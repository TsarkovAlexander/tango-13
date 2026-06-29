def test_lambda_broker_exposes_mangum_handler() -> None:
    from mangum import Mangum

    from sandbox_executor.lambda_broker import app, handler

    assert app.title == "Tango Lambda MicroVM Broker"
    assert isinstance(handler, Mangum)
