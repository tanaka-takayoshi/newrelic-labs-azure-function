import logging
import datetime
import time
import os
import typing

import azure.functions as func

from opentelemetry import propagators, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import BatchExportSpanProcessor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace.propagation.textmap import DictGetter
from opentelemetry_ext_newrelic import NewRelicSpanExporter

def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    # Function名をサービス名（エンティティ名）として設定
    trace.set_tracer_provider(
        TracerProvider(resource=Resource.create({"service.name": context.function_name}))
    )

    # New Relicへの送信用APIキーの設定（Functionで環境変数にキーを追加しておく）
    newrelic = NewRelicSpanExporter(
                os.environ["NEW_RELIC_INSERT_KEY"],
            )

    trace.get_tracer_provider().add_span_processor(
        BatchExportSpanProcessor(
            newrelic,
            schedule_delay_millis=500,
        )
    )
    
    logging.info('Python HTTP trigger function processed a request.')

    tracer = trace.get_tracer("root")
    # Httpヘッダーから抽出したcontextを設定することで分散トレーシングをつなげる
    with tracer.start_as_current_span('format', context=propagators.extract(DictGetter(), req.headers)) as span:
        # 呼び出しごとに一意なinvocation idを属性として設定
        span.set_attribute("invocation.id", context.invocation_id)
        time.sleep(0.5)
        name = req.params.get('name')

        if not name:
            try:
                req_body = req.get_json()
            except ValueError:
                pass
            else:
                name = req_body.get('name')

    # レスポンスを返す前に shutdown()を呼び出してデータを送信する
    newrelic.shutdown()
    if name:
        return func.HttpResponse(f"Hello, {name}. This HTTP triggered function executed successfully.",
        headers={"Access-Control-Allow-Headers": "newrelic,traceparent,tracestate"})
    else:
        return func.HttpResponse(
        "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
            status_code=200,
            headers={"Access-Control-Allow-Headers": "newrelic,traceparent,tracestate"}
        )
