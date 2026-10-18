"""Generate a source-backed inventory of the preserved application for the Next.js rewrite."""
import ast
import csv
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.main import app, create_app
from app.core.config import Settings

OUT = ROOT / 'docs/nextjs'
OUT.mkdir(parents=True, exist_ok=True)
operations = []
for name, application in [('operational', app), ('cloud', create_app(Settings(
        deployment_mode='cloud_gateway', cloud_runtime_database_url='postgresql+psycopg://audit@127.0.0.1/unused_inventory', _env_file=None)))]:
    schema = application.openapi()
    (OUT / f'{name}-openapi.json').write_text(json.dumps(schema, indent=2) + '\n')
    for path, methods in schema['paths'].items():
        for method, operation in methods.items():
            if method.upper() not in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'}:
                continue
            operations.append({'runtime': name, 'method': method.upper(), 'path': path,
                               'module': ', '.join(operation.get('tags', [])),
                               'purpose': operation.get('summary', ''),
                               'authentication': 'Protected' if operation.get('security') else 'See source policy',
                               'operation_id': operation.get('operationId', '')})
with (OUT / 'API_ROUTE_INVENTORY.csv').open('w', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(operations[0]), lineterminator="\n"); writer.writeheader(); writer.writerows(operations)
lines = ['# Existing API route inventory', '', 'Generated from the preserved FastAPI OpenAPI documents. These are source contracts, not a claim of Next.js parity.', '',
         '| Runtime | Method | Route | Area | Purpose |', '| --- | --- | --- | --- | --- |']
lines += [f"| {r['runtime']} | {r['method']} | `{r['path']}` | {r['module']} | {r['purpose']} |" for r in operations]
(OUT / 'API_ROUTE_INVENTORY.md').write_text('\n'.join(lines) + '\n')
functions = []
for file in sorted((ROOT / 'backend/app/services').glob('*.py')):
    tree = ast.parse(file.read_text())
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            functions.append({'file': str(file.relative_to(ROOT)), 'name': node.name,
                              'kind': 'class' if isinstance(node, ast.ClassDef) else 'function',
                              'line': node.lineno, 'purpose': (ast.get_docstring(node) or '').split('\n')[0]})
with (OUT / 'SERVICE_FUNCTION_INVENTORY.csv').open('w', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(functions[0]), lineterminator="\n"); writer.writeheader(); writer.writerows(functions)
summary = {'source_commit': subprocess.check_output(['git', 'rev-parse', '5d36734'], cwd=ROOT).decode().strip(),
           'operational_paths': len(app.openapi()['paths']),
           'operational_operations': sum(r['runtime']=='operational' for r in operations),
           'cloud_operations': sum(r['runtime']=='cloud' for r in operations),
           'service_files': len(list((ROOT/'backend/app/services').glob('*.py'))),
           'top_level_service_functions_and_classes': len(functions),
           'page_modules': len(list((ROOT/'frontend/src/pages').glob('*.tsx')))}
(OUT / 'SOURCE_INVENTORY.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
