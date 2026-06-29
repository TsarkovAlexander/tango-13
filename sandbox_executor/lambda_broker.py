from mangum import Mangum

from sandbox_executor.microvm_broker import create_app


app = create_app()
handler = Mangum(app)
