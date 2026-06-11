import io
from datetime import date, datetime

import pandas as pd
from django.http import HttpResponse
from django.utils.translation import gettext as _

from .pdf_utils import _get_answer_content, _get_respondent_name

DATE_FORMAT = '%d.%m.%Y'


def _question_column_headers(questions):
    """Build unique column headers from question text, suffixing duplicates."""
    seen = {}
    headers = []
    for question in questions:
        text = question.question_text
        count = seen.get(text, 0) + 1
        seen[text] = count
        if count > 1:
            headers.append(f"{text} ({count})")
        else:
            headers.append(text)
    return headers


def _format_date_dd_mm_yyyy(value):
    """Format a date value as DD.MM.YYYY for Excel export."""
    if isinstance(value, datetime):
        return value.strftime(DATE_FORMAT)
    if isinstance(value, date):
        return value.strftime(DATE_FORMAT)

    if isinstance(value, str) and value:
        for fmt in ('%Y-%m-%d', DATE_FORMAT, '%d/%m/%Y'):
            try:
                return datetime.strptime(value, fmt).strftime(DATE_FORMAT)
            except ValueError:
                continue
    return value


def _format_answer_for_excel(question, content):
    """Format answer content for Excel, applying date formatting where needed."""
    if not content:
        return ''
    if question.question_type == 'date':
        return _format_date_dd_mm_yyyy(content)
    return content


def generate_survey_all_responses_excel(survey):
    """Generate an Excel workbook with one row per completed response."""
    questions = list(survey.questions.all())
    question_headers = _question_column_headers(questions)

    responses = survey.responses.filter(is_complete=True).order_by(
        'submitted_at'
    ).prefetch_related(
        'answers__question',
        'answers__selected_options',
    )

    rows = []
    for survey_response in responses:
        answers_by_question = {
            answer.question_id: answer for answer in survey_response.answers.all()
        }

        row = {}
        if not survey.responses_are_anonymous:
            row[_("Participant")] = _get_respondent_name(survey_response)

        row[_("Submitted")] = survey_response.submitted_at.strftime(DATE_FORMAT)

        for question, header in zip(questions, question_headers):
            answer = answers_by_question.get(question.id)
            if answer:
                content = _get_answer_content(answer)
                row[header] = _format_answer_for_excel(question, content)
            else:
                row[header] = ''

        rows.append(row)

    df = pd.DataFrame(rows)
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer.getvalue()


def create_excel_response(excel_content, filename):
    """Create HTTP response for Excel download."""
    response = HttpResponse(
        excel_content,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
