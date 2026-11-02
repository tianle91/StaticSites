"""Deployment contract: generated application assets never depend on the repo."""
from pathlib import Path
import re
import pytest

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = sorted(path.parent for path in ROOT.glob('*/Makefile'))


@pytest.mark.parametrize('project', PROJECTS, ids=lambda path:path.name)
def test_generated_html_has_no_build_time_runtime_dependencies(project):
    html = (project/'output'/f'{project.name}.html').read_text(encoding='utf-8')
    assert '__MAP_TABS__' not in html
    assert '__EXPLORER_JS__' not in html
    assert '__EXPLORER_CSS__' not in html
    assert '__QUERY_JS__' not in html
    assert 'src/staticsites' not in html
    scripts = re.findall(r'<script\b[^>]*\bsrc=["\']([^"\']+)',html,re.I)
    styles = re.findall(r'<link\b[^>]*\bhref=["\']([^"\']+)',html,re.I)
    assert all(url.startswith(('https://','http://','data:')) for url in scripts + styles)
    if project.name in ('canada-mortgage-stress','fcf-macro-indicators','margin-sp500-m2-visualization'):
        assert scripts == [] and styles == []

