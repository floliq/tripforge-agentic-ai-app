from datetime import date

from models import TripRequest


def test_trip_request_is_complete():
    assert TripRequest(city="Moscow", days=3).is_complete()
    assert TripRequest(
        city="Moscow", date_from=date(2026, 6, 1), date_to=date(2026, 6, 3)
    ).is_complete()
    assert TripRequest(city="Rome", days=5).is_complete()

    assert not TripRequest().is_complete()
    assert not TripRequest(city="Moscow").is_complete()
    assert not TripRequest(city="Moscow", date_from=date(2026, 6, 1)).is_complete()
    assert not TripRequest(city="Moscow", date_to=date(2026, 6, 3)).is_complete()


def test_friends_weekend_not_complete_until_clarified():
    draft = TripRequest(
        raw_request="Спланируй поездку в выходные к друзьям",
        trip_purpose="friends",
        time_hint="weekend",
    )
    assert not draft.is_complete()

    clarified = draft.model_copy(update={"city": "Prague", "days": 2})
    assert clarified.is_complete()


def test_rome_this_month_not_complete_until_dates():
    draft = TripRequest(
        raw_request="Хочу поехать в Рим в этом месяце",
        city="Rome",
        time_hint="this month",
    )
    assert not draft.is_complete()

    clarified = draft.model_copy(
        update={"date_from": date(2026, 5, 10), "date_to": date(2026, 5, 14)}
    )
    assert clarified.is_complete()
