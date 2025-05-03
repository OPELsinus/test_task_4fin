import json
import os
import random

from python_task.src.models import Request, Response
from random import choice


def new_client_strategy(score: float) -> dict:
    result = 1 if score < 0.15 else 0

    return {
        'strategy': 'new_client_strategy',
        'result': str(result),
        'loan_amount': 6_000 if result == 1 else None,
        'loan_term': 3 if result == 1 else None
    }


def repeat_client_strategy(score: float) -> dict:

    result = 1 if score < 0.20 else 0

    return {
        'strategy': 'repeat_client_strategy',
        'result': str(result),
        'loan_amount': 12_000 if result == 1 else None,
        'loan_term': 6 if result == 1 else None
    }


def pilot_repeat_client_strategy(score: float, sql_data: dict) -> dict | None:

    phone_number = str(sql_data.get('phone_number', ''))

    if not phone_number.endswith(('2', '4')):
        return None

    result = 1 if score < 0.18 else 0

    return {
        'strategy': 'pilot_repeat_client_strategy',
        'result': str(result),
        'loan_amount': 24_000 if result == 1 else None,
        'loan_term': 12 if result == 1 else None
    }


def pure_stream_strategy_chance() -> bool:
    return random.randint(1, 100) <= 5


def main(request: Request) -> Response:
    application_data_path = request.context / "Application" / "Application.json"
    application_data = json.loads(application_data_path.read_text())

    # TODO: Implement your scoring logic here
    client_type = application_data.get('client_type')

    scoring_file_path = None
    for dir_name in os.listdir(request.context):
        if 'pythonscoring' in str(dir_name).lower():
            for file in os.listdir(os.path.join(request.context, dir_name)):
                scoring_file_path = request.context / str(dir_name) / str(file)

    scoring_data = json.loads(scoring_file_path.read_text()) if scoring_file_path is not None else {}
    score = scoring_data.get('score', None)

    if score is None:
        raise Exception(f'No score file for {request.context}')

    sql_data_path = request.context / "SqlIntegration" / "SqlIntegration.json"
    sql_data = json.loads(sql_data_path.read_text())

    if pure_stream_strategy_chance():
        return Response(
            strategy_name=choice(["pure_stream_strategy"]),
            result="1",
            score=score,
            loan_amount=8_000,
            loan_term=6,
        )

    response_data = dict()
    if client_type == 'new':
        response_data = new_client_strategy(score=score)

    if client_type == 'repeat':
        response_data = pilot_repeat_client_strategy(score=score, sql_data=sql_data)
        if response_data is None:
            response_data = repeat_client_strategy(score=score)

    return Response(
        strategy_name=response_data.get('strategy', ''),
        result=response_data.get('result', 'error'),
        score=score,
        loan_amount=response_data.get('loan_amount', None),
        loan_term=response_data.get('loan_term', None),
    )
