from app.core.errors import ApiError, Conflict, Locked, NotFound


def test_api_error_envelope_shape():
    err = ApiError(error="boom", message="it broke", status_code=418, details={"field": "x"})
    env = err.to_envelope()
    assert env == {"error": "boom", "message": "it broke", "details": {"field": "x"}}
    assert err.status_code == 418


def test_not_found_defaults():
    err = NotFound()
    assert err.status_code == 404
    assert err.to_envelope()["error"] == "not_found"


def test_conflict_carries_code():
    err = Conflict("deadline_passed_no_makeup", "too late")
    assert err.status_code == 409
    assert err.to_envelope()["error"] == "deadline_passed_no_makeup"


def test_locked_status():
    err = Locked()
    assert err.status_code == 423
    assert err.to_envelope()["error"] == "account_locked"


def test_details_default_to_empty_dict():
    env = ApiError(error="x", message="y").to_envelope()
    assert env["details"] == {}
