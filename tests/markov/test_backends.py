from poxbot.features.markov.backends import MarkovifyBackend
from poxbot.features.markov.model import MarkovModel
from poxbot.features.markov.tokenizer import MarkovTokenizer


def test_markovify_backend_generates_from_existing_model() -> None:
    model = MarkovModel(order=2)
    tokenizer = MarkovTokenizer()
    backend = MarkovifyBackend(model, tokenizer)

    backend.train(tokenizer.tokenize('hello world'))
    backend.train(tokenizer.tokenize('hello there'))

    generated = backend.generate_tokens(max_tokens=10)

    assert generated
    assert len(generated) <= 10
    assert all(token not in {model.START, model.END} for token in generated)


def test_markovify_backend_respects_seed() -> None:
    model = MarkovModel(order=2)
    tokenizer = MarkovTokenizer()
    backend = MarkovifyBackend(model, tokenizer)

    backend.train(tokenizer.tokenize('hello world again'))
    backend.train(tokenizer.tokenize('hello world today'))

    generated = backend.generate_tokens(
        max_tokens=10,
        seed='hello world',
    )

    assert generated
    assert generated[0] in {'again', 'today'}
