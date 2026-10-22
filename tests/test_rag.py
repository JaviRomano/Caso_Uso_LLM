"""Recuperación (sin Ollama) e integridad de la base de conocimiento y de las consultas de evaluación."""

import json

from caso_uso_llm.paths import EVALS
from caso_uso_llm.rag import kb
from caso_uso_llm.rag.eval_retrieval import load_queries, per_query
from caso_uso_llm.rag.retrieve import BM25, Doc, Retriever, rrf, tokenize


def test_tokenize_quita_tildes_palabras_vacias_y_recorta():
    assert tokenize("La habitación NO tenía aire") == ["habit", "no", "tenia", "aire"]


def test_bm25_prefiere_el_documento_con_los_terminos():
    s = BM25(["el desayuno era muy rico", "la piscina estaba sucia", "reembolso de la reserva"])
    assert s.scores("quiero un reembolso").argmax() == 2


def test_rrf_premia_lo_que_aparece_arriba_en_ambos_rankings():
    assert rrf([[0, 1, 2], [1, 0, 2]])[:2] == [0, 1]
    assert rrf([[2, 0, 1], [2, 1, 0]])[0] == 2


def test_retriever_lexico_sin_embeddings():
    docs = [Doc("a", "politica", "ruido de la calle"), Doc("b", "politica", "limpieza de sábanas")]
    assert Retriever(docs).search("mucho ruido", k=1, method="bm25")[0].id == "a"


def test_per_query_recall_y_mrr():
    m = per_query(["x", "a", "b", "y"], ["a", "b"])
    assert m["recall@1"] == 0 and m["recall@3"] == 1 and m["mrr"] == 0.5


def test_ids_unicos_y_material_sintetico():
    for name in ("politicas.json", "respuestas_aprobadas.json", "fichas_hoteles.json"):
        data = json.loads((kb.KB / name).read_text(encoding="utf-8"))
        assert data["is_synthetic"] is True
    for docs in (kb.politicas(include_always=True), kb.respuestas()):
        assert len({d.id for d in docs}) == len(docs)
    assert all(r.payload["hotel"] in kb.fichas() for r in kb.respuestas())


def test_politicas_siempre_no_se_buscan():
    siempre = {p["id"] for p in kb.politicas_siempre()}
    assert siempre and not siempre & {d.id for d in kb.politicas()}


def test_consultas_etiquetadas_con_ids_existentes_y_sin_fuga():
    pol, resp = {d.id for d in kb.politicas()}, {d.id for d in kb.respuestas()}
    reviews = {d.text for d in kb.respuestas()}
    queries = load_queries()
    assert len({q["id"] for q in queries}) == len(queries)
    for q in queries:
        assert q["politicas"] and set(q["politicas"]) <= pol, q["id"]
        assert set(q["respuestas"]) <= resp, q["id"]
        assert q["texto"] not in reviews, q["id"]  # la consulta no puede ser una reseña indexada
    raw = json.loads((EVALS / "retrieval" / "consultas_v1.json").read_text(encoding="utf-8"))
    assert raw["is_synthetic"] is True


def test_ficha_texto_lista_los_servicios():
    texto = kb.ficha_texto("h02")
    assert "Granada" in texto and "Spa: No hay." in texto


def test_ficha_checks_detectan_servicio_inexistente_cifras_y_contradiccion():
    from caso_uso_llm.rag.generate_rag import ficha_checks

    # h02 no tiene spa ni parking; desayuno a 9 €
    c = ficha_checks("Le esperamos en nuestro spa. El parking cuesta 12 €.", "Todo bien.", "h02")
    assert set(c["servicio_inexistente"]) == {"spa", "parking"} and c["cifra_inventada"] == ["12 €"]
    assert not ficha_checks("El desayuno cuesta 9 €.", "Bien.", "h02")["cifra_inventada"]
    assert ficha_checks("Sí había carteles en la piscina.", "No había carteles.", "h04")[
        "contradice"
    ]
    # Si el cliente lo menciona, nombrarlo no es inventarlo
    assert not ficha_checks("Sentimos lo del spa.", "No había spa.", "h02")["servicio_inexistente"]


def test_los_prompts_rag_son_v4_mas_su_bloque_de_contexto():
    from caso_uso_llm.generate.prompts import RAG_PROMPTS, RESPONSE_PROMPTS
    from caso_uso_llm.spec import CONTEXTOS

    for v in RAG_PROMPTS:
        assert RESPONSE_PROMPTS[v] == RESPONSE_PROMPTS["v4"] + "\n\n" + CONTEXTOS[v]
    assert CONTEXTOS["v6"].startswith(CONTEXTOS["v5"])


def test_ficha_checks_importe_y_fuente_interna():
    from caso_uso_llm.rag.generate_rag import ficha_checks

    c = ficha_checks("En nuestra ficha el desayuno cuesta 12 €.", "Caro.", "h08")
    assert c["importe"] == ["12 €"] and c["nombra_fuente"]
    assert ficha_checks("Gracias por su visita.", "Bien.", None) == {
        "importe": [],
        "nombra_fuente": False,
        "servicio_inexistente": [],
        "cifra_inventada": [],
        "contradice": False,
    }
