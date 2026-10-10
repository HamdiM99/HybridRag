"""Compréhension de requête : transforme le texte libre RH en filtres + requête
sémantique, pour que "10 ans dans le conseil" devienne un filtre vérifiable
plutôt qu'une simple similarité vectorielle (qui a tendance à diluer les
contraintes numériques)."""
from cvsearch.config import get_settings
from cvsearch.llm.clients import chat_client
from cvsearch.llm.prompts import QUERY_UNDERSTANDING_SYSTEM, query_understanding_user_prompt
from cvsearch.schema import SearchFilters


def understand_query(query: str) -> SearchFilters:
    settings = get_settings()
    client = chat_client()
    resp = client.chat.completions.parse(
        model=settings.chat_deployment,
        messages=[
            {"role": "system", "content": QUERY_UNDERSTANDING_SYSTEM},
            {"role": "user", "content": query_understanding_user_prompt(query)},
        ],
        max_completion_tokens=settings.max_completion_tokens,
        reasoning_effort=settings.reasoning_effort,
        response_format=SearchFilters,
    )
    parsed = resp.choices[0].message.parsed
    if parsed is None:
        # Repli robuste : recherche purement sémantique si la compréhension échoue.
        return SearchFilters(semantic_query=query)
    return parsed
