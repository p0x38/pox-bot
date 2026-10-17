from poxbot.features.earthquake.p2pquake import EEW, EVENT_ADAPTER


def test_eew_accepts_null_areas() -> None:
    event = EVENT_ADAPTER.validate_python(
        {
            '_id': 'test-event',
            'time': '2026-10-16T12:48:54+09:00',
            'code': 556,
            'issue': {
                'time': '2026-10-16T12:48:54+09:00',
                'eventId': 'test-event',
                'serial': '1',
            },
            'cancelled': False,
            'areas': None,
        },
    )

    assert isinstance(event, EEW)
    assert event.areas == []
