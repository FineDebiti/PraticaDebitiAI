import time
from app.workers.celery_app import celery_app
from app.db import SessionLocal
from app.models import (
    Case, Document, Extraction, Creditor, DebtPosition, RealEstate,
    Company, CompanyMember, FinancialStatement, FinancialIndicator,
    CreditExposure, GuaranteeGiven, CreditReportSummary, Debtor,
)
from app.services import ocr, llm
from app.services import estratto_conto_parser as ecp
from app.services import fiscal_code as fc
from app.services.indicators import compute_indicators
from app.config import settings

# Tipi che usano l'estrazione multimodale (Gemini legge il file direttamente).
# Le visure, la CR e il bilancio hanno layout/tabelle che il modello legge meglio dall'immagine.
MULTIMODAL_TYPES = {"visura_catastale", "visura_camerale", "centrale_rischi", "bilancio",
                    "dichiarazione_redditi", "busta_paga"}


@celery_app.task(name="app.workers.tasks.process_document")
def process_document(document_id: str):
    db = SessionLocal()
    t0 = time.time()
    try:
        doc = db.get(Document, document_id)
        if not doc:
            return
        doc.status = "in_elaborazione"
        db.commit()

        # CF del titolare = punto fermo della pratica, lo passiamo all'estrazione
        case = db.get(Case, doc.case_id)
        client_cf = case.client_tax_code if case else ""

        # 1) OCR/parser per estrarre testo
        text, pages = ocr.extract_text(doc.storage_path)

        # Tipo gia imposto dall'upload mirato (es. tasto "Carica bilancio")? salta la classificazione.
        forced = doc.doc_type and doc.doc_type != "da_classificare"
        if forced:
            doc_type, conf = doc.doc_type, 1.0
        else:
            cls = llm.classify(text)
            doc_type, conf = cls["doc_type"], cls["confidence"]

        # 2) Estrazione: estratto conto -> parser tabellare gratuito (AI Flash solo
        #    se il parser non legge la tabella); visure/bilancio -> multimodale (se
        #    Gemini); tutti gli altri -> da testo OCR.
        if doc_type == "estratto_conto":
            try:
                data = ecp.parse_pdf(doc.storage_path)
            except ecp.EstrattoContoParseError as e:
                print(f"[ec] parser fallito ({e}) -> fallback AI Flash", flush=True)
                data = llm.extract(text, doc_type, client_cf)
                # l'AI ritorna i movimenti ma non le aggregazioni: le calcoliamo qui
                # (stesse medie deterministiche del parser) per il mapping reddito.
                if not data.get("aggregazioni"):
                    mov = []
                    for m in (data.get("movimenti") or []):
                        d = m.get("data")
                        if not d:
                            continue
                        mov.append({"data": d, "dare": abs(_num(m.get("dare"))),
                                    "avere": abs(_num(m.get("avere")))})
                    if mov:
                        data["aggregazioni"] = ecp._aggregate(mov, data.get("saldo_finale"))
        elif doc_type in MULTIMODAL_TYPES and settings.llm_provider == "gemini":
            data = llm.extract_from_file(doc.storage_path, doc_type, client_cf)
        else:
            data = llm.extract(text, doc_type, client_cf)

        # Alcuni provider (per via di _COMMON_RULES) incapsulano OGNI campo come
        # {value, confidence, page}: srotoliamo SOLO questo pattern, una volta, così
        # tutti i consumatori a valle (mapping reddito, pannelli, savers) vedono scalari.
        data = _unwrap_confidence(data)

        doc.doc_type = doc_type
        doc.classification_confidence = conf
        doc.num_pages = pages

        # Re-processing: una sola Extraction per documento. Senza questa pulizia ogni
        # rielaborazione accodava una riga in più e la relazione uselist=False poteva
        # restituire quella VECCHIA (es. modello/estrazione superati).
        for old in db.query(Extraction).filter_by(document_id=doc.id).all():
            db.delete(old)
        db.flush()

        ext = Extraction(
            document_id=doc.id, ocr_provider=settings.ocr_provider,
            llm_provider=settings.llm_provider, raw_text=text[:20000],
            json_output=data, duration_ms=int((time.time() - t0) * 1000),
        )
        db.add(ext)

        # 3a) Documenti patrimoniali (visura catastale) -> salva immobili
        for imm in data.get("immobili", []) or []:
            rendita = _num(imm.get("rendita_catastale"))
            quota = imm.get("quota_soggetto") or ""
            cat = imm.get("categoria") or ""
            db.add(RealEstate(
                case_id=doc.case_id,
                kind=_imm_kind(imm),
                address=imm.get("indirizzo") or "",
                cadastral_data=_cadastral(imm),
                ownership_share=quota,
                ownership_right=imm.get("diritto_soggetto") or "",
                surface_mq=_num(imm.get("superficie_mq")),
                cadastral_income=rendita,
                cadastral_value=_valore_catastale(rendita, cat, quota),
                category=cat,
                commercial_value=0.0,  # placeholder: calcolo ad hoc in futuro
                other_owners=_altri_intestatari(imm),
                provenance=imm.get("provenienza") or "",
                notes=_imm_notes(imm),
            ))

        # 3a-bis) Visura camerale -> salva azienda + soci
        if data.get("impresa"):
            _save_company(db, doc, data, client_cf)

        # 3a-ter) Centrale Rischi -> esposizioni, garanzie prestate, sintesi
        if data.get("document_type") == "centrale_rischi" or data.get("esposizione_attuale"):
            _save_credit_report(db, doc, data)

        # 3a-quater) Bilancio -> azienda + statement + indici calcolati
        if data.get("doc_type") == "bilancio" or data.get("stato_patrimoniale"):
            _save_financial_statement(db, doc, data, client_cf)

        # 3a-quinquies) Documenti reddituali -> PROPONGONO valori nei campi economici
        # del Debtor (human-in-the-loop: riempie solo i campi vuoti, l'operatore rivede).
        if doc_type in ("busta_paga", "cu", "isee", "estratto_conto", "dichiarazione_redditi"):
            _apply_income_to_debtor(db, doc.case_id, doc_type, data)

        # 3b) Documenti debitori -> salva creditori e posizioni
        for pos in data.get("credit_positions", []) or []:
            name = (pos.get("creditor") or "").strip()
            if name and not _creditor_exists(db, doc.case_id, name):
                db.add(Creditor(case_id=doc.case_id, name=name, source_document_id=doc.id))
            db.add(DebtPosition(
                case_id=doc.case_id,
                creditor_name=name,
                debt_type=pos.get("debt_type") or "",
                original_amount=_num(pos.get("original_amount")),
                residual_amount=_num(pos.get("residual_amount")),
                overdue_amount=_num(pos.get("overdue_amount")),
                monthly_installment=_num(pos.get("monthly_installment")),
                status=pos.get("status") or "",
                confidence=_num(pos.get("confidence")),
                source_document_id=doc.id,
                source_page=int(pos.get("source_page") or 0),
            ))

        doc.status = "elaborato"
        doc.error = ""   # ripulisce un eventuale errore di un tentativo precedente
        db.commit()
    except Exception as e:
        db.rollback()
        doc = db.get(Document, document_id)
        if doc:
            doc.status = "errore"
            doc.error = str(e)[:500]
            db.commit()
    finally:
        db.close()


def _unwrap_confidence(obj):
    """Srotola il pattern {value, confidence, page} (indotto da _COMMON_RULES) ovunque
    nell'albero JSON, lasciando INTATTI i veri oggetti annidati (es. {corrente,
    precedente}, i quadri della dichiarazione, gli elenchi di immobili/movimenti)."""
    _wrap_keys = {"value", "confidence", "page", "source_page", "conf", "pagina"}
    if isinstance(obj, dict):
        if "value" in obj and set(obj.keys()) <= _wrap_keys:
            return _unwrap_confidence(obj["value"])
        return {k: _unwrap_confidence(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_unwrap_confidence(x) for x in obj]
    return obj


def _num(v):
    if isinstance(v, dict):           # difesa: campo ancora incapsulato {value,...}
        v = v.get("value")
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _creditor_exists(db, case_id, name):
    return db.query(Creditor).filter_by(case_id=case_id, name=name).first() is not None


# ---------------- Reddito: documenti -> campi economici del Debtor ----------------
def _set_income_note(debtor, tag: str, text: str):
    """Aggiorna income_sources con una riga tracciata per fonte (idempotente):
    rimuove l'eventuale riga precedente con lo stesso tag e ne riscrive una nuova."""
    lines = [l for l in (debtor.income_sources or "").split("\n")
             if l.strip() and not l.startswith(tag)]
    lines.append(f"{tag} {text}".strip())
    debtor.income_sources = "\n".join(lines)


def _apply_income_to_debtor(db, case_id: str, doc_type: str, data: dict):
    """Mappa i dati estratti dai documenti reddituali sui campi del Debtor.

    PRINCIPIO (spec §5 minimale, human-in-the-loop): i valori vengono PROPOSTI nei
    campi economici riempiendo SOLO quelli ancora vuoti (non si sovrascrive il dato
    già inserito dall'operatore); una nota tracciabile resta in income_sources.
    Questi campi alimentano il cruscotto (red_capacita_rimborso)."""
    debtor = db.query(Debtor).filter_by(case_id=case_id).first()
    if not debtor:
        return

    if doc_type == "busta_paga":
        netto = _num(data.get("retribuzione_netta"))
        # NB: non scrive più monthly_net_income (lo conferma l'operatore via "Applica"
        # del Riepilogo reddito): così il campo non diverge mai dal cruscotto.
        datore = data.get("datore_lavoro") or ""
        if datore and not debtor.employer:
            debtor.employer = datore
        periodo = data.get("periodo") or ""
        _set_income_note(debtor, "[Busta paga]",
                         f"netto {_eur(netto)}/mese" + (f" · {periodo}" if periodo else "")
                         + (f" · {datore}" if datore else ""))

    elif doc_type == "cu":
        annuo = _num(data.get("reddito_complessivo"))
        # non scrive più annual_income: lo propone il Riepilogo reddito, l'operatore applica.
        anno = data.get("anno") or ""
        _set_income_note(debtor, "[CU]",
                         f"reddito complessivo {_eur(annuo)}" + (f" · anno {anno}" if anno else ""))

    elif doc_type == "isee":
        isee = _num(data.get("isee_ordinario"))
        anno = data.get("anno") or ""
        scad = data.get("scadenza") or ""
        nucleo = data.get("componenti_nucleo")
        nota = f"ISEE {_eur(isee)}"
        if anno:
            nota += f" · anno {anno}"
        if nucleo:
            nota += f" · nucleo {int(_num(nucleo))}"
        if scad:
            nota += f" · scad. {scad}"
        _set_income_note(debtor, "[ISEE]", nota)

    elif doc_type == "estratto_conto":
        agg = data.get("aggregazioni") or {}
        entrate = _num(agg.get("entrate_medie_mensili"))
        uscite = _num(agg.get("uscite_medie_mensili"))
        # non scrive più monthly_net_income: i flussi sono lordi e restano un riferimento
        # nel Riepilogo reddito; il reddito lo conferma l'operatore.
        _set_income_note(debtor, "[Estratto conto]",
                         f"entrate medie {_eur(entrate)}/mese · uscite {_eur(uscite)}/mese")

    elif doc_type == "dichiarazione_redditi":
        rn = data.get("riepilogo_RN") or {}
        quadri = data.get("quadri") or {}
        annual = _num(rn.get("reddito_complessivo"))
        # NB: la dichiarazione NON scrive più i campi piatti (annual_income/monthly):
        # il complessivo è eterogeneo (anno e fonte diversi dalla busta paga) e creava
        # riepiloghi incoerenti. Contribuisce SOLO al Riepilogo reddito consolidato
        # (services/income_summary.py) + alla nota qui sotto. L'operatore applica il
        # mensile consolidato dal riepilogo.
        # sintesi delle fonti di reddito per quadro -> income_sources (non resta vuoto)
        fonti = []
        for key, label, amount_key in [
            ("RB_fabbricati", "affitti", "canoni_percepiti"),
            ("RE_lavoro_autonomo", "lavoro autonomo", "reddito"),
            ("RF_RG_impresa", "impresa", "reddito"),
            ("RH_partecipazioni", "partecipazioni", "reddito"),
            ("RC_lavoro_dipendente", "lavoro dipendente", "reddito"),
            ("RA_terreni", "terreni", "reddito"),
            ("RL_altri_redditi", "altri redditi", "reddito"),
        ]:
            q = quadri.get(key) or {}
            if not q.get("presente"):
                continue
            val = _num(q.get(amount_key)) or _num(q.get("reddito"))
            extra = ""
            if key == "RB_fabbricati":
                n = int(_num(q.get("n_immobili_locati")))
                extra = f" ({n} immobil{'e' if n == 1 else 'i'} locat{'o' if n == 1 else 'i'})" if n else ""
            fonti.append(f"{label} {_eur(val)}/anno{extra}")
        anno = data.get("anno_imposta") or ""
        modello = "Mod. 730" if data.get("modello") == "730" else "Mod. Redditi PF"
        nota = f"complessivo {_eur(annual)}/anno"
        if fonti:
            nota += " · " + "; ".join(fonti)
        if anno:
            nota += f" · anno {anno}"
        nota += f" · {modello}"
        _set_income_note(debtor, "[Dichiarazione redditi]", nota)


def _eur(v) -> str:
    return f"€ {(_num(v)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _save_company(db, doc, data: dict, client_cf: str = ""):
    """Salva l'impresa estratta da una visura camerale + i suoi soci.

    Il MATCHING del cliente e DETERMINISTICO via codice fiscale (punto fermo della
    pratica): un socio e il cliente se il suo CF coincide con quello del titolare.
    Vale anche se l'impresa stessa ha il CF del cliente (ditta individuale)."""
    imp = data.get("impresa") or {}
    soci = data.get("soci", []) or []

    # marca i soci col CF del titolare (override certo sulla stima dell'AI)
    for s in soci:
        s["e_cliente"] = bool(s.get("e_cliente")) or fc.same(s.get("codice_fiscale", ""), client_cf)

    # cliente se: un socio ha il CF del titolare, OPPURE l'impresa stessa ha quel CF
    has_client = any(s.get("e_cliente") for s in soci) or fc.same(imp.get("codice_fiscale", ""), client_cf)
    company = Company(
        case_id=doc.case_id,
        role="cliente" if has_client else "controparte",
        name=imp.get("denominazione") or "",
        legal_form=imp.get("forma_giuridica") or "",
        company_type=imp.get("tipo_societa") or "",
        tax_code=imp.get("codice_fiscale") or "",
        vat=imp.get("partita_iva") or "",
        rea=imp.get("numero_rea") or "",
        cciaa=imp.get("cciaa") or "",
        pec=imp.get("pec") or "",
        legal_address=imp.get("sede_legale") or "",
        status=imp.get("stato_attivita") or "",
        constitution_date=imp.get("data_costituzione") or "",
        capital=_num(imp.get("capitale_conferimenti")),
        business_summary=imp.get("oggetto_sociale_sintesi") or "",
        extra=data.get("dati_secondari") or {},
        source_document_id=doc.id,
    )
    db.add(company)
    db.flush()  # serve l'id per i soci
    for s in soci:
        db.add(CompanyMember(
            company_id=company.id,
            name=s.get("denominazione") or "",
            tax_code=s.get("codice_fiscale") or "",
            is_client=bool(s.get("e_cliente")),
            roles=", ".join(s.get("cariche", []) or []),
            is_legal_rep=bool(s.get("rappresentante_legale")),
            quota_value=_num(s.get("quota_valore")),
            quota_percent=_num(s.get("quota_percentuale")),
        ))


def _save_credit_report(db, doc, data: dict):
    """Salva la sintesi della Centrale Rischi: esposizioni, garanzie prestate, totali."""
    rec = data.get("data_riferimento_piu_recente") or ""

    for e in data.get("esposizione_attuale", []) or []:
        db.add(CreditExposure(
            case_id=doc.case_id,
            intermediary=e.get("intermediario") or "",
            category=e.get("categoria") or "",
            accordato=_num(e.get("accordato")),
            utilizzato=_num(e.get("utilizzato")),
            importo_garantito=_num(e.get("importo_garantito")),
            status=e.get("stato_rapporto") or "",
            is_critical=bool(e.get("e_critico")),
            reference_month=rec,
            source_document_id=doc.id,
        ))

    for g in data.get("garanzie_prestate", []) or []:
        db.add(GuaranteeGiven(
            case_id=doc.case_id,
            intermediary=g.get("intermediario") or "",
            guaranteed_subject=g.get("soggetto_garantito") or "",
            valore_garanzia=_num(g.get("valore_garanzia")),
            importo_garantito=_num(g.get("importo_garantito")),
            status=g.get("stato") or "",
            source_document_id=doc.id,
        ))

    tot = data.get("totali") or {}
    periodo = data.get("periodo") or {}
    db.add(CreditReportSummary(
        case_id=doc.case_id,
        period_from=periodo.get("da") or "",
        period_to=periodo.get("a") or "",
        most_recent_month=rec,
        num_intermediaries=int(tot.get("numero_intermediari") or 0),
        total_exposure=_num(tot.get("esposizione_totale_utilizzata")),
        total_guarantees=_num(tot.get("totale_garanzie_prestate")),
        has_sofferenze=bool(tot.get("presenza_sofferenze")),
        has_criticita=bool(tot.get("presenza_criticita")),
        criticita=data.get("criticita") or [],
        source_document_id=doc.id,
        **_llm_meta(data),
    ))


def _cur(blk: dict, key: str) -> float:
    """Valore 'corrente' di una voce {corrente,precedente} (0 se assente)."""
    v = (blk or {}).get(key)
    return _num(v.get("corrente")) if isinstance(v, dict) else 0.0


def _llm_meta(data: dict) -> dict:
    """Estrae provenienza ed esito cross-check aggiunti da llm.py, da persistere."""
    cc = data.get("_crosscheck") or {}
    return {
        "llm_provider": data.get("_llm_provider") or "",
        "llm_model": data.get("_llm_model") or "",
        "crosscheck_status": cc.get("status") or "",
        "crosscheck_payload": cc if cc else {},
    }


def _save_financial_statement(db, doc, data: dict, client_cf: str = ""):
    """Salva il bilancio: aggancia/crea la Company (match P.IVA/CF), salva il
    FinancialStatement (raw §2) e gli indici calcolati in modo deterministico."""
    az = data.get("azienda") or {}
    sp = data.get("stato_patrimoniale") or {}
    ce = data.get("conto_economico") or {}
    deb = data.get("debiti_per_natura") or {}
    piva = az.get("partita_iva") or ""
    cf = az.get("codice_fiscale") or ""
    ateco = az.get("ateco") or ""

    # match deterministico su una Company esistente della pratica (P.IVA o CF)
    company = None
    for c in db.query(Company).filter_by(case_id=doc.case_id).all():
        if (piva and fc.same(c.vat, piva)) or (cf and fc.same(c.tax_code, cf)):
            company = c
            break
    if not company:
        # nessuna azienda collegata: la creo dai dati del bilancio (cliente se CF combacia)
        is_client = fc.same(cf, client_cf) or fc.same(piva, client_cf)
        company = Company(
            case_id=doc.case_id, role="cliente" if is_client else "controparte",
            name=az.get("denominazione") or "", vat=piva, tax_code=cf, ateco=ateco,
            legal_form=az.get("forma_giuridica") or "", legal_address=az.get("sede") or "",
            capital=_num(az.get("capitale_sociale")), source_document_id=doc.id,
        )
        db.add(company)
        db.flush()
    elif ateco and not company.ateco:
        company.ateco = ateco  # arricchisci se mancante

    priv = _num((deb.get("tributari") or {}).get("importo")) + _num((deb.get("previdenziali") or {}).get("importo"))
    stmt = FinancialStatement(
        company_id=company.id, case_id=doc.case_id,
        fiscal_year_end=(data.get("esercizio") or {}).get("data_chiusura") or "",
        statement_type=(data.get("esercizio") or {}).get("tipo") or "",
        ateco=ateco, raw_extraction=data,
        total_assets=_cur(sp, "totale_attivo"), equity=_cur(sp, "patrimonio_netto"),
        total_debts=_cur(sp, "debiti_totali"), revenues=_cur(ce, "ricavi_vendite"),
        net_result=_cur(ce, "utile_perdita"),
        debts_secured=bool(data.get("debiti_assistiti_garanzie_reali")),
        privileged_debts=priv, source_document_id=doc.id,
        **_llm_meta(data),
    )
    db.add(stmt)
    db.flush()
    for ind in compute_indicators(sp, ce, deb, ateco):
        db.add(FinancialIndicator(statement_id=stmt.id, **ind))


def _imm_kind(imm: dict) -> str:
    cat = imm.get("categoria")
    tipo = imm.get("tipo_immobile") or ""
    return f"{tipo} {cat}".strip() if cat else (tipo or "immobile")


def _cadastral(imm: dict) -> str:
    parts = []
    for label, key in [("Sez", "sezione_urbana"), ("Fg", "foglio"),
                       ("Part", "particella"), ("Sub", "subalterno")]:
        v = imm.get(key)
        if v:
            parts.append(f"{label} {v}")
    com = imm.get("comune")
    head = f"{com} - " if com else ""
    return head + " ".join(parts)


def _imm_notes(imm: dict) -> str:
    bits = []
    if imm.get("consistenza"):
        bits.append(f"Consistenza: {imm['consistenza']}")
    if imm.get("piano"):
        bits.append(f"Piano: {imm['piano']}")
    if imm.get("classe"):
        bits.append(f"Classe: {imm['classe']}")
    return " | ".join(bits)


def _altri_intestatari(imm: dict) -> str:
    out = []
    for o in imm.get("altri_intestatari", []) or []:
        nome = o.get("denominazione") or "?"
        quota = o.get("quota") or ""
        diritto = o.get("diritto") or ""
        out.append(f"{nome} ({diritto} {quota})".strip())
    return "; ".join(out)


# Moltiplicatori per il VALORE CATASTALE (rendita rivalutata 5% x moltiplicatore).
# Riferimento normativo standard (seconde case / fabbricati non prima casa).
_MOLT = {
    "A": 120, "A/10": 60, "B": 140,
    "C": 120, "C/1": 40, "C/6": 120, "C/7": 120,
    "D": 60, "E": 40,
}


def _moltiplicatore(categoria: str) -> int:
    if not categoria:
        return 0
    cat = categoria.upper().strip()
    if cat in _MOLT:
        return _MOLT[cat]
    gruppo = cat.split("/")[0]  # "A/2" -> "A"
    return _MOLT.get(gruppo, 0)


def _quota_frazione(quota: str) -> float:
    """Converte '1/3' -> 0.333..., '1/1' -> 1.0. Ritorna 1.0 se non interpretabile."""
    if not quota:
        return 1.0
    q = quota.strip()
    if "/" in q:
        try:
            n, d = q.split("/")
            return float(n) / float(d) if float(d) else 1.0
        except (ValueError, ZeroDivisionError):
            return 1.0
    return 1.0


def _valore_catastale(rendita: float, categoria: str, quota: str, prima_casa: bool = False) -> float:
    """Valore catastale = rendita x 1,05 x moltiplicatore, sulla QUOTA del soggetto.
    Per le abitazioni (gruppo A, esclusa A/10) il moltiplicatore prima casa e 110 invece di 120.
    Dato oggettivo di legge (non valore di mercato). 0 se categoria non mappata."""
    molt = _moltiplicatore(categoria)
    if prima_casa and categoria:
        gruppo = categoria.upper().split("/")[0]
        if gruppo == "A" and categoria.upper() != "A/10":
            molt = 110
    if not rendita or not molt:
        return 0.0
    valore_pieno = rendita * 1.05 * molt
    return round(valore_pieno * _quota_frazione(quota), 2)
