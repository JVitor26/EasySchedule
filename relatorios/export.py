from openpyxl import Workbook
from django.http import HttpResponse


def exportar_excel(dados, nome="relatorio.xlsx"):
    wb = Workbook()
    ws = wb.active

    if isinstance(dados, list) and len(dados) > 0:
        headers = dados[0].keys()
        ws.append(list(headers))

        for row in dados:
            ws.append(list(row.values()))

    elif isinstance(dados, dict):
        for key, value in dados.items():
            ws.append([key, value])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename={nome}'

    wb.save(response)
    return response