import math

from poxbot.features.chatbot.tfidf import TfidfIndex


def test_cosine_similarity_is_one_for_identical_documents() -> None:
    index = TfidfIndex()
    index.fit(
        [
            ('hello', 'world'),
        ]
    )

    assert math.isclose(
        index.cosine_similarity(('hello', 'world'), ('hello', 'world')), 1.0
    )


def test_rank_prefers_matching_terms() -> None:
    index = TfidfIndex()
    index.fit(
        [
            ('how', 'install', 'python'),
            ('how', 'cook', 'rice'),
            ('hello', 'everyone'),
        ]
    )

    ranked = index.rank(('install', 'python'))

    assert ranked[0][0] == 0
    assert ranked[0][1] > ranked[1][1]


def test_empty_documents_have_zero_similarity() -> None:
    index = TfidfIndex()
    index.fit([('hello',)])

    assert math.isclose(index.cosine_similarity((), ('hello',)), 0.0)
    assert math.isclose(index.cosine_similarity(('hello',), ()), 0.0)
