"""Offline atlas contracts, not native UI proofs; JS execution optionally uses Node."""
import ast
import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

REPOSITORY = Path(__file__).resolve().parents[1]
ROOT = REPOSITORY / 'docs' / 'diagramas'
COMPLETE_ORDER = (
    'purpose.html', 'structure.html', 'data-journey.html',
    'installer-transaction.html', 'setup-assist.html', 'proof-harness.html',
    'proof-cases.html', 'lifecycle-verify.html', 'installer-states.html',
    'resource-ownership.html', 'claim-traceability.html', 'harness-failures.html',
)
# Registration is deliberate: a missing registered file is always an error.
DELIVERED_PAGES = (
    'purpose.html', 'structure.html', 'data-journey.html', 'installer-transaction.html',
    'setup-assist.html', 'proof-harness.html', 'proof-cases.html', 'lifecycle-verify.html',
    'installer-states.html', 'resource-ownership.html', 'claim-traceability.html',
    'harness-failures.html',
)
GROUPS = {
    'product': COMPLETE_ORDER[:3],
    'installer': COMPLETE_ORDER[3:7],
    'combined': COMPLETE_ORDER[7:8],
    'responsibility': COMPLETE_ORDER[8:],
}
TITLES = (
    'Purpose and boundaries', 'Internal structure', 'Data journey',
    'Installer transaction', 'Setup assistance', 'Reusable transport',
    'Evidence boundaries', 'Build, run and verify',
)


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.stack = []
        self.texts = []
        self.links = []
        self.buttons = []
        self.elements = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.elements.append((tag, attrs))
        if tag == 'a':
            self.links.append(attrs['href'])
        if tag == 'button':
            self.buttons.append(attrs)
        if tag not in {'meta', 'br', 'hr', 'input', 'link', 'img'}:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def handle_endtag(self, tag):
        if tag in self.stack:
            self.stack = self.stack[:len(self.stack) - 1 - self.stack[::-1].index(tag)]

    def handle_data(self, text):
        if not set(self.stack) & {'style', 'script', 'code', 'button'} and text.strip():
            self.texts.append(text.strip())


def read(name):
    return (ROOT / name).read_text(encoding='utf-8')


def translations(source):
    match = re.search(r'const translations = (\{.*?\});', source, re.S)
    assert match, 'standalone translation dictionary required'
    return json.loads(match[1])


def validate_registry(root, delivered):
    assert len(delivered) == len(set(delivered)), 'duplicate registration'
    assert set(delivered) <= set(COMPLETE_ORDER), 'unknown registration'
    assert tuple(name for name in COMPLETE_ORDER if name in delivered) == delivered
    assert {p.name for p in root.glob('*.html')} == {'index.html', *delivered}
    assert (root / 'index.html').read_text(encoding='utf-8').strip()
    for name in ('index.html', *delivered):
        for href in Page((root / name).read_text(encoding='utf-8')).links:
            target = urlsplit(href)
            if target.path.endswith('.html'):
                assert target.path in {'index.html', *delivered}, href


def source_reference(href):
    """Map only pinned, tracked GitHub source anchors; never fetch or read history."""
    target = urlsplit(href)
    assert target.scheme == 'https' and target.netloc == 'github.com', href
    assert '?' not in href and not target.query and href == target.geturl(), href
    assert not any(character.isspace() for character in href), href
    match = re.fullmatch(
        r'/dnieblesdev/yasb-limitora/blob/([0-9a-f]{40})/([A-Za-z0-9_./-]+)', target.path,
    )
    assert match, href
    repository_path = match[2]
    assert all(part not in {'', '.', '..'} for part in repository_path.split('/')), href
    assert not repository_path.startswith('docs/diagramas/'), 'atlas navigation stays local'
    tracked = set(subprocess.check_output(
        ['git', 'ls-files', '-z'], cwd=REPOSITORY,
    ).decode().split('\0'))
    assert repository_path in tracked, href
    linked = (REPOSITORY / repository_path).resolve()
    assert linked.is_relative_to(REPOSITORY) and linked.is_file(), href
    line_range = re.fullmatch(r'L(\d+)-L(\d+)', target.fragment)
    assert line_range, href
    first, last = map(int, line_range.groups())
    assert 1 <= first <= last <= len(linked.read_text(encoding='utf-8').splitlines()), href
    return linked, target.fragment


def assert_source_target(source, repository_path, fragment):
    expected = ((REPOSITORY / repository_path).resolve(), fragment)
    assert expected in {source_reference(href) for href in Page(source).links
                        if urlsplit(href).scheme}, expected


def test_published_source_url_maps_to_repository_file():
    href = ('https://github.com/dnieblesdev/yasb-limitora/blob/'
            + 'a' * 40 + '/src/yasb_limitora/cli.py#L187-L200')
    assert source_reference(href) == (REPOSITORY / 'src/yasb_limitora/cli.py', 'L187-L200')


@pytest.mark.parametrize('suffix', (
    'https://example.invalid/dnieblesdev/yasb-limitora/blob/{revision}/src/yasb_limitora/cli.py#L1-L2',
    'https://github.com/other/yasb-limitora/blob/{revision}/src/yasb_limitora/cli.py#L1-L2',
    'https://github.com/dnieblesdev/other/blob/{revision}/src/yasb_limitora/cli.py#L1-L2',
    'http://github.com/dnieblesdev/yasb-limitora/blob/{revision}/src/yasb_limitora/cli.py#L1-L2',
    'https://user@github.com/dnieblesdev/yasb-limitora/blob/{revision}/src/yasb_limitora/cli.py#L1-L2',
    'https://github.com:443/dnieblesdev/yasb-limitora/blob/{revision}/src/yasb_limitora/cli.py#L1-L2',
    'https://github.com/dnieblesdev/yasb-limitora/blob/main/src/yasb_limitora/cli.py#L1-L2',
    'https://github.com/dnieblesdev/yasb-limitora/blob/{revision}/src/../cli.py#L1-L2',
    'https://github.com/dnieblesdev/yasb-limitora/blob/{revision}/src/%2e%2e/cli.py#L1-L2',
    'https://github.com/dnieblesdev/yasb-limitora/blob/{revision}/src%2fyasb_limitora/cli.py#L1-L2',
    'https://github.com/dnieblesdev/yasb-limitora/blob/{revision}/missing.py#L1-L2',
    'https://github.com/dnieblesdev/yasb-limitora/blob/{revision}/docs/diagramas/index.html#L1-L2',
    'https://github.com/dnieblesdev/yasb-limitora/blob/{revision}/src/yasb_limitora/cli.py?q=1#L1-L2',
    'https://github.com/dnieblesdev/yasb-limitora/blob/{revision}/src/yasb_limitora/cli.py#L2-L1',
    'https://github.com/dnieblesdev/yasb-limitora/blob/{revision}/src/yasb_limitora/cli.py#L0-L2',
    'https://github.com/dnieblesdev/yasb-limitora/blob/{revision}/src/yasb_limitora/cli.py#L1-L999999',
    'https://github.com/dnieblesdev/yasb-limitora/blob/{revision}/src/yasb_limitora/cli.py',
))
def test_published_source_url_rejects_unapproved_targets(suffix):
    with pytest.raises(AssertionError):
        source_reference(suffix.format(revision='a' * 40))


def assert_local_url_references(source):
    for value in re.findall(r'url\s*\(([^)]*)\)', source, re.I):
        value = value.strip().strip('\"\'')
        assert re.fullmatch(r'#[\w-]+', value), 'no external CSS assets'


def test_fragment_markers_allowed_but_external_assets_rejected():
    assert_local_url_references('<path marker-end="url(#arrow)"/>')
    for value in ('https://example.invalid/font.woff2', '//example.invalid/image',
                  'image.png', 'data:image/png;base64,AAAA'):
        with pytest.raises(AssertionError, match='no external CSS assets'):
            assert_local_url_references(f'background:url("{value}")')


def assert_offline_assets(page):
    for tag, attrs in page.elements:
        assert tag != 'link', 'no loaded external assets'
        if tag != 'a':
            for key in ('src', 'href', 'srcset', 'poster', 'data'):
                if key in attrs:
                    assert not urlsplit(attrs[key]).scheme and not attrs[key].startswith('//'), (
                        'no loaded external assets'
                    )


@pytest.mark.parametrize('markup', (
    '<script src="https://github.com/dnieblesdev/yasb-limitora/blob/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/src/yasb_limitora/cli.py#L1-L2"></script>',
    '<img src="https://example.invalid/image.png">',
    '<link rel="stylesheet" href="https://example.invalid/style.css">',
    '<svg><image href="//example.invalid/image.svg"/></svg>',
    '<iframe src="https://github.com/"></iframe>',
    '<object data="https://example.invalid/document"></object>',
))
def test_source_anchor_permission_never_permits_loaded_remote_assets(markup):
    with pytest.raises(AssertionError, match='no loaded external assets'):
        assert_offline_assets(Page(markup))


def test_registered_inventory_and_nonempty_index():
    validate_registry(ROOT, DELIVERED_PAGES)


def test_registry_rejects_missing_registered_page(tmp_path):
    (tmp_path / 'index.html').write_text('<h1>Atlas</h1>', encoding='utf-8')
    with pytest.raises(AssertionError):
        validate_registry(tmp_path, ('purpose.html',))


def test_registry_rejects_undelivered_link(tmp_path):
    (tmp_path / 'index.html').write_text(
        '<a href="purpose.html">Pending</a>', encoding='utf-8')
    with pytest.raises(AssertionError, match='purpose.html'):
        validate_registry(tmp_path, ())


@pytest.mark.parametrize('name', ('index.html', *DELIVERED_PAGES))
def test_standalone_i18n_and_accessibility(name):
    source = read(name)
    page = Page(source)
    dictionary = translations(source)
    # Theme adds a button; language membership belongs to language controls only.
    language_buttons = [button for button in page.buttons if 'data-language' in button]
    assert len(language_buttons) == 2
    assert {button['data-language'] for button in language_buttons} == {'es', 'en'}
    assert 'id="language-controls" hidden' in source
    assert 'lang="en"' in source  # coherent no-JS fallback
    stable = r'[\w. /–:+-]+:\d+–\d+|[.;:]|yasb-limitora|YASB CustomWidget|ExecutionOrchestrator|RefreshAttempt|stdout / stderr / exit status'
    for text in page.texts:
        if not re.fullmatch(stable, text):
            assert text in dictionary, text
            assert dictionary[text].strip(), text
    for label in re.findall(r'data-i18n-label="([^"]+)"', source):
        assert label in dictionary
        assert f'aria-label="{label}"' in source
    for required in (
        "document.querySelectorAll('[data-i18n-label]')", '[hidden]{display:none!important}',
        '#language-controls [aria-pressed=true]', ':focus-visible',
        '@media(max-width:640px)', "localStorage.getItem('yasb-limitora-language')",
        "localStorage.setItem('yasb-limitora-language'", 'node.textContent',
    ):
        assert required in source
    for forbidden in ('innerHTML', 'role="tab"', 'onclick='):
        assert forbidden not in source
    assert not re.search(r'<link\b|@import', source)
    assert_offline_assets(page)
    assert_local_url_references(source)
    assert not re.search(r'<script[^>]+src=', source)
    assert source.endswith('\n')
    assert not any(line.rstrip() != line for line in source.splitlines())


@pytest.mark.parametrize('name', ('index.html', *DELIVERED_PAGES))
def test_links_resolve_to_tracked_or_authored_files(name):
    tracked = set(subprocess.check_output(
        ['git', 'ls-files', '-z'], cwd=REPOSITORY,
    ).decode().split('\0'))
    authored = {f'docs/diagramas/{page}' for page in ('index.html', *DELIVERED_PAGES)}
    for tag, attrs in Page(read(name)).elements:
        if tag != 'a':
            continue
        href = attrs['href']
        target = urlsplit(href)
        if target.scheme or target.netloc:
            linked, _ = source_reference(href)
            assert attrs.get('target') == '_blank'
            assert set(attrs.get('rel', '').split()) == {'noopener', 'noreferrer'}
        else:
            assert not target.query and unquote(target.path) == target.path, href
            assert target.path in {'', 'index.html', *DELIVERED_PAGES}, href
            linked = ((ROOT / target.path) if target.path else ROOT / name).resolve()
        relative = linked.relative_to(REPOSITORY).as_posix()
        assert relative in tracked | authored, href
        assert linked.is_file(), href
        contents = linked.read_text(encoding='utf-8')
        line_range = re.fullmatch(r'L(\d+)-L(\d+)', target.fragment)
        if line_range:
            first, last = map(int, line_range.groups())
            assert 1 <= first <= last <= len(contents.splitlines()), href
        elif target.fragment:
            assert f'id="{target.fragment}"' in contents, href
        if relative not in authored:
            assert source_reference(href) == (linked, target.fragment)


@pytest.mark.parametrize('name', ('index.html', *DELIVERED_PAGES))
def test_sections_and_filled_dot_markers(name):
    source = read(name)
    marker = re.search(r'\.section-nav a::before\{([^}]+)\}', source)[1]
    assert 'border-radius:50%' in marker
    paint = re.search(r'background:([^;]+)', marker)[1]
    assert resolve_paint(paint, theme_palette(source)) == '#4f5d75'
    assert resolve_paint(paint, theme_palette(source, dark=True)) == '#bfc0c0'
    assert 'border:2px' not in marker
    navigation = re.search(r'<nav class="section-nav"[^>]*>(.*?)</nav>', source, re.S)[1]
    prefix = '#' if name == 'index.html' else 'index.html#'
    for area in GROUPS:
        assert f'href="{prefix}{area}"' in navigation
    assert 'data-i18n-label="Sections"' in source
    if name != 'index.html':
        area = next(area for area, names in GROUPS.items() if name in names)
        assert f'href="index.html#{area}" aria-current="location"' in navigation
        assert navigation.count('aria-current="location"') == 1


def test_progressive_index_and_original_display_texts():
    source = read('index.html')
    assert 'id="proof"' in source
    assert 'id="responsibility"' in source
    for title in TITLES:
        assert f'<h3>{title}</h3>' in source
    cards = re.findall(r'<a class="atlas-card" href="([^"]+)">(.*?)</a>', source, re.S)
    assert tuple(href for href, _ in cards) == DELIVERED_PAGES
    for href, content in cards:
        assert re.search(r'<h3>[^<]+</h3>', content), href
        assert re.search(r'<p>[^<]+</p>', content), href
        assert 'class="card-enter" aria-hidden="true"' in content
        area = next(area for area, names in GROUPS.items() if href in names)
        section = re.search(rf'<section id="{area}"[^>]*>(.*?)</section>', source, re.S)[1]
        assert f'href="{href}"' in section
    assert f'Available: {len(DELIVERED_PAGES)} / Planned: {len(COMPLETE_ORDER)}' in source


@pytest.mark.parametrize('name', DELIVERED_PAGES)
def test_progressive_page_navigation_and_stable_code(name):
    source = read(name)
    assert 'class="area-nav"' in source
    assert f'href="{name}" aria-current="page"' in source
    assert source.count('aria-current="page"') == 1
    for label in ('Area navigation', 'Language', 'Breadcrumb'):
        assert f'data-i18n-label="{label}"' in source
    assert 'class="breadcrumb"' in source
    area = next(names for names in GROUPS.values() if name in names)
    area_navigation = re.search(r'<nav class="area-nav"[^>]*>(.*?)</nav>', source, re.S)[1]
    assert Page(area_navigation).links == [page for page in area if page in DELIVERED_PAGES]
    index = DELIVERED_PAGES.index(name)
    previous = DELIVERED_PAGES[index - 1] if index else 'index.html'
    following = DELIVERED_PAGES[index + 1] if index + 1 < len(DELIVERED_PAGES) else 'index.html'
    assert f'rel="prev" href="{previous}"' in source
    assert f'rel="next" href="{following}"' in source
    assert f'<span class="progress">View {index + 1} / {len(DELIVERED_PAGES)}</span>' in source
    assert 'Source links open the published GitHub revision with pinned line anchors; clicking them requires a network connection, but the atlas renders offline.' in ' '.join(Page(source).texts)
    assert "closest('script, style, code, button')" in source


@pytest.mark.parametrize('name', DELIVERED_PAGES)
def test_scroll_hint_and_explicit_legends(name):
    source = read(name)
    english = 'Scroll horizontally to see the full diagram'
    figure = re.search(r'<figure\b.*?</figure>', source, re.S)[0]
    assert f'<p class="scroll-hint">{english}</p>' in figure
    assert figure.index('class="scroll-hint"') < figure.index('class="diagram-container"')
    dictionary = translations(source)
    assert dictionary[english] == 'Deslizá horizontalmente para ver el diagrama completo'
    for required in (
        'figure{container-type:inline-size}', '.scroll-hint{display:none;',
        '@container(width < 1280px){.scroll-hint{display:block}}',
        '@media print{.scroll-hint{display:none}}', 'min-width:1280px', 'overflow-x:auto',
    ):
        assert required in source
    for english, spanish in dictionary.items():
        if english.startswith('Solid →'):
            assert spanish.startswith('Línea continua →')


def node_bounds(node):
    rect = node.find('{http://www.w3.org/2000/svg}rect')
    if rect is not None:
        return tuple(float(rect.attrib[key]) for key in ('x', 'y', 'width', 'height'))
    polygon = node.find('{http://www.w3.org/2000/svg}polygon')
    assert polygon is not None, 'node must have a real rectangle or polygon'
    coordinates = [float(value) for value in re.split(r'[\s,]+', polygon.attrib['points'].strip())]
    assert len(coordinates) >= 6 and len(coordinates) % 2 == 0
    xs, ys = coordinates[::2], coordinates[1::2]
    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)


def test_real_polygon_bounds_without_synthetic_rectangle():
    node = ET.fromstring('<g xmlns="http://www.w3.org/2000/svg">'
                         '<polygon points="640,136 760,192 640,248 520,192"/></g>')
    assert node_bounds(node) == (520, 136, 240, 112)


@pytest.mark.parametrize('name', DELIVERED_PAGES)
def test_accessible_svg_budget_bounds_and_nonoverlap(name):
    svg = ET.fromstring(re.search(r'<svg\b.*?</svg>', read(name), re.S)[0])
    ns = {'s': 'http://www.w3.org/2000/svg'}
    assert svg.attrib['role'] == 'img'
    assert svg.attrib['aria-labelledby'] == f'{Path(name).stem}-title {Path(name).stem}-desc'
    assert svg[0].tag == f'{{{ns["s"]}}}title'
    assert svg[0].text
    assert svg.find('s:desc', ns).text
    nodes = svg.findall('.//*[@data-node]')
    arrows = svg.findall('.//*[@marker-end]')
    assert 1 <= len(nodes) <= 9
    assert len(arrows) <= 12
    expected = {'proof-harness.html': (7, 6), 'proof-cases.html': (6, 0),
                'lifecycle-verify.html': (9, 8)}
    if name in expected:
        assert (len(nodes), len(arrows)) == expected[name]
    if name in ('installer-transaction.html', 'setup-assist.html'):
        assert len(nodes) >= 4
    boxes = []
    for node in nodes:
        x, y, width, height = node_bounds(node)
        assert 40 <= x < x + width <= 1240
        assert 40 <= y < y + height <= 660
        for px, py, pw, ph in boxes:
            assert not (x < px + pw and px < x + width and y < py + ph and py < y + height)
        boxes.append((x, y, width, height))
        for text in node.findall('s:text', ns):
            assert x + 16 <= float(text.attrib['x']) <= x + width - 16
            assert y + 16 <= float(text.attrib['y']) <= y + height - 16
    for edge in svg.findall('s:path', ns):
        assert not re.search(r'[LlAaCcSsTt]', edge.attrib['d'])


@pytest.mark.parametrize('name', tuple(name for name in DELIVERED_PAGES if name == 'purpose.html'))
def test_purpose_ownership_and_resolved_source_links(name):
    source = read(name)
    svg = ET.fromstring(re.search(r'<svg\b.*?</svg>', source, re.S)[0])
    assert {node.attrib['data-node'] for node in svg.findall('.//*[@data-node]')} == {
        'yasb', 'cli', 'limitora',
    }
    assert len(svg.findall('.//*[@marker-end]')) == 3
    assert '<code>execution_state, execution_error, general, providers</code>' in source
    assert 'Native CLI proof is not automated YASB rendering proof.' in source
    for repository_path, fragment in (
        ('docs/architecture/README.md', 'L1-L47'),
        ('src/yasb_limitora/cli.py', 'L187-L334'),
    ):
        assert_source_target(source, repository_path, fragment)


@pytest.mark.parametrize('name', tuple(name for name in DELIVERED_PAGES if name == 'structure.html'))
def test_structure_nodes_and_resolved_source_links(name):
    source = read(name)
    svg = ET.fromstring(re.search(r'<svg\b.*?</svg>', source, re.S)[0])
    assert {node.attrib['data-node'] for node in svg.findall('.//*[@data-node]')} == {
        'cli', 'coordinator', 'orchestrator', 'attempt', 'executors', 'adapter', 'projection',
    }
    assert len(svg.findall('.//*[@marker-end]')) == 6
    for filename, fragment in (
        ('cli.py', 'L187-L334'), ('worker.py', 'L436-L673'),
        ('codex_helper.py', 'L644-L708'), ('limitora_api.py', 'L330-L364'),
        ('projection.py', 'L484-L563'),
    ):
        assert_source_target(source, f'src/yasb_limitora/{filename}', fragment)


@pytest.mark.parametrize('name', tuple(name for name in DELIVERED_PAGES if name == 'data-journey.html'))
def test_data_journey_decision_and_resolved_source_links(name):
    source = read(name)
    svg = ET.fromstring(re.search(r'<svg\b.*?</svg>', source, re.S)[0])
    nodes = svg.findall('.//*[@data-node]')
    assert {node.attrib['data-node'] for node in nodes} == {
        'configuration', 'freshness', 'reuse', 'claim', 'providers',
        'sanitize', 'cleanup', 'projection', 'stdout',
    }
    assert len(svg.findall('.//*[@marker-end]')) == 9
    decision = next(node for node in nodes if node.attrib['data-node'] == 'freshness')
    assert decision.find('{http://www.w3.org/2000/svg}rect') is None
    assert node_bounds(decision) == (520, 136, 240, 112)
    for repository_path, fragment in (
        ('src/yasb_limitora/cli.py', 'L187-L334'),
        ('src/yasb_limitora/cache.py', 'L1169-L1300'),
        ('src/yasb_limitora/worker.py', 'L436-L673'),
        ('src/yasb_limitora/limitora_api.py', 'L330-L364'),
        ('src/yasb_limitora/projection.py', 'L484-L563'),
        ('docs/architecture/README.md', 'L63-L109'),
    ):
        assert_source_target(source, repository_path, fragment)


@pytest.mark.parametrize('name', tuple(
    name for name in DELIVERED_PAGES if name == 'installer-transaction.html'
))
def test_installer_transaction_recovery_caveats_and_source_links(name):
    source = read(name)
    public_text = ' '.join(Page(source).texts)
    for claim in (
        'DeinitializeSetup restores only while an evacuation remains uncommitted.',
        'Failed checked deletion at commit raises an exception and preserves recovery state.',
        'failure may retain recovery bytes instead of restoring automatically.',
        'Not an automatic installer rollback',
        'never imports prior registration before proven byte restoration.',
        'This is an explanatory source view, not new installer or VM proof.',
    ):
        assert claim in public_text
    svg = ET.fromstring(re.search(r'<svg\b.*?</svg>', source, re.S)[0])
    assert {node.attrib['data-node'] for node in svg.findall('.//*[@data-node]')} == {
        'gate', 'evacuate', 'native', 'commit', 'assist', 'uninstall',
        'quarantine', 'restore', 'registry',
    }
    assert len(svg.findall('.//*[@marker-end]')) == 8
    for fragment in ('L1-L45', 'L222-L448', 'L904-L952'):
        assert_source_target(source, 'packaging/inno/yasb-limitora.iss', fragment)


@pytest.mark.parametrize('name', tuple(name for name in DELIVERED_PAGES if name == 'setup-assist.html'))
def test_setup_assist_active_transport_consent_and_source_links(name):
    source = read(name)
    public_text = ' '.join(Page(source).texts)
    for claim in (
        'Build operations JSON in Inno', 'Set private request environment variable',
        'Launch installed CLI with private sentinel', 'Exit 0 / 1 → Inno',
        'This route does not read result.json.',
        'no operations means no launch.',
        'Configuration rollback is separate and remains guarded by lease ownership.',
        'does not automatically reverse the committed native installation.',
        'The separately supported nonce-directory request.json / result.json transport is not the active Inno path.',
    ):
        assert claim in public_text
    for identifier in ('_YASB_SETUP_ASSIST_REQUEST', '--__yasb-limitora-setup-assist'):
        assert f'<code>{identifier}</code>' in source.split('<script>')[0]
    svg = ET.fromstring(re.search(r'<svg\b.*?</svg>', source, re.S)[0])
    assert {node.attrib['data-node'] for node in svg.findall('.//*[@data-node]')} == {
        'postcommit', 'uninstall', 'request', 'validate', 'execute', 'exit',
    }
    assert len(svg.findall('.//*[@marker-end]')) == 5
    for repository_path, fragments in (
        ('packaging/inno/SetupAssistant.isi', ('L1-L12', 'L198-L298')),
        ('src/yasb_limitora/setup_assist.py', ('L163-L224', 'L494-L565', 'L675-L703')),
    ):
        for fragment in fragments:
            assert_source_target(source, repository_path, fragment)


@pytest.mark.parametrize('name', tuple(name for name in DELIVERED_PAGES if name == 'proof-harness.html'))
def test_proof_harness_integrity_limits_and_resolved_source_links(name):
    source = read(name)
    public_text = ' '.join(Page(source).texts)
    for claim in (
        'is an explicit opt-in to writable input, not a read-only mode.',
        'Pre/post input-tree hashes detect persistent mutation, not transient tamper reverted before the post-hash.',
        'Only verified controlled success requests shutdown.',
        'reports timeout as exit 124.',
        'it is not produced by the guest or synthesized for old archives.',
    ):
        assert claim in public_text
    assert '<code>-AllowWritableInputIntegrityFallback</code>' in source.split('<script>')[0]
    for repository_path, fragments in (
        ('proof-harness/README.md', ('L5-L18', 'L43-L68')),
        ('proof-harness/guest/bootstrap-watch.ps1',
         ('L43-L57', 'L252-L300', 'L425-L478')),
    ):
        for fragment in fragments:
            assert_source_target(source, repository_path, fragment)


@pytest.mark.parametrize('name', tuple(name for name in DELIVERED_PAGES if name == 'proof-cases.html'))
def test_proof_cases_resolved_historical_source_links(name):
    source = read(name)
    for repository_path, fragments in (
        ('proof-harness/README.md', ('L79-L120',)),
        ('docs/release/0.2.0/evidence/issue-304-reusable-vm-proof.md', ('L1-L47',)),
        ('docs/release/0.2.0/evidence/s11b-c5-silent-uninstall-state-root.md',
         ('L3-L58', 'L99-L111')),
        ('proof-harness/guest/run-c5-silent-uninstall.ps1', ('L14-L21',)),
    ):
        for fragment in fragments:
            assert_source_target(source, repository_path, fragment)


@pytest.mark.parametrize('name', tuple(
    name for name in DELIVERED_PAGES if name == 'lifecycle-verify.html'
))
def test_lifecycle_candidate_branch_and_repository_source_links(name):
    source = read(name)
    svg = ET.fromstring(re.search(r'<svg\b.*?</svg>', source, re.S)[0])
    assert {node.attrib['data-node'] for node in svg.findall('.//*[@data-node]')} == {
        'source', 'frozen', 'candidate', 'install', 'cli', 'boundary',
        'vm', 'evidence', 'verifier',
    }
    branch = next(edge for edge in svg.findall('{http://www.w3.org/2000/svg}path')
                  if edge.attrib['data-to'] == 'vm')
    assert branch.attrib['data-from'] == 'candidate'
    assert branch.attrib['stroke-dasharray'] == '5,4'
    for repository_path, fragments in (
        ('scripts/build_setup.py', ('L85-L120', 'L154-L199')),
        ('packaging/inno/yasb-limitora.iss', ('L27-L45',)),
        ('docs/architecture/README.md', ('L1-L47',)),
        ('proof-harness/README.md', ('L43-L68',)),
        ('docs/release/0.2.0/RELEASE_NOTES.md', ('L1-L8',)),
    ):
        for fragment in fragments:
            assert_source_target(source, repository_path, fragment)


@pytest.mark.parametrize('name', tuple(
    name for name in DELIVERED_PAGES if name == 'installer-states.html'
))
def test_installer_states_artifacts_guards_and_responsibility(name):
    source = read(name)
    page = Page(source)
    public_text = ' '.join(page.texts)
    for claim in (
        'No durable journal and no automatic crash resume.',
        'An absent APP returns successful preparation before the stale .old check.',
        'APP absent + .old present + .failed absent passes preparation without snapshot export or rename.',
        'A stale .failed aborts preparation even when APP is absent.',
        'No independent stale .old.reg gate: export /y can overwrite an earlier snapshot when APP exists.',
        'Ownership means path and registry coherence plus file existence, not exact content hashes.',
        'Uninstaller launch failure or nonzero exit logs and continues filesystem rollback.',
        'Zero exit enables a bounded cleanup wait; APP still present after that wait aborts rollback.',
        'Partial DelTree failure may already destroy prior bytes; retained flags do not guarantee a complete old payload.',
        'Registry import failure retains the snapshot, not an automatic resume mechanism.',
        'PENDING: native proof of the current Pascal rollback and interruption paths.',
        'The historical fallback shares the product AppId but uses a disposable path and harness-initiated uninstall and restore.',
    ):
        assert claim in public_text
    for artifact in ('APP', 'APP.old', 'APP.failed', 'APP.old.reg', 'HKCU',
                     'EvacuatedOldDir', 'PriorRegistrySnapshot', 'FailedQuarantineOwned'):
        assert f'<code>{artifact}</code>' in source.split('<script>')[0]
    assert '<table' in source and '<caption>' in source and 'scope="col"' in source
    svg = ET.fromstring(re.search(r'<svg\b.*?</svg>', source, re.S)[0])
    assert len(svg.findall('.//*[@data-node]')) == 9
    assert len(svg.findall('.//*[@marker-end]')) == 8
    assert_source_target(source, 'tests/test_inno_script.py', 'L214-L248')
    assert_source_target(source, 'docs/release/0.2.0/evidence/inno-staged-swap-spike.md', 'L125-L149')


@pytest.mark.parametrize('name', tuple(
    name for name in DELIVERED_PAGES if name == 'resource-ownership.html'
))
def test_resource_ownership_matrix_authority_and_retention(name):
    source = read(name)
    rows = re.findall(r'<tr data-resource="([^"]+)">(.*?)</tr>', source, re.S)
    assert [key for key, _ in rows] == [
        'app', 'old', 'failed', 'snapshot', 'uninstall-key', 'path-record',
        'path-entry', 'config', 'state-cache', 'input-vhdx', 'evidence-vhdx',
        'vm-checkpoint', 'archive-provenance',
    ]
    for key, row in rows:
        assert row.count('<td>') == 5, key
        assert 'scope="row"' in row and '<a href=' in row, key
        assert 'PENDING' in row, key
    public_text = ' '.join(Page(source).texts)
    for claim in (
        'A filename alone is not deletion authority; process globals are not durable ownership.',
        'Inno ownership is path and registry coherence plus file existence, not content-hash identity.',
        'No independent stale snapshot gate; export /y may overwrite an earlier snapshot.',
        'PATH removal requires the recorded full live value and type to match, including the final owned element.',
        'Configuration rollback is attempted only after replacement and while the lease remains owned; it can fail.',
        'The host finally attempts disk detach and image dismount, not VM, checkpoint, VHDX or archive deletion.',
        'Hot-detach may succeed while the VM is running; running state alone does not prove detachment failure.',
        'Writable fallback is explicit opt-in; pre/post hashes detect persistent mutation only, not read-only or hostile-guest protection.',
        'The generic checkpoint is operator-provisioned with OS and bootstrap only, not scenario payload.',
        'No automatic edits to user YASB YAML or CSS; provider detection, authentication and transport remain Limitora responsibilities.',
        'Reading a test is not executing it. PENDING means no exact-current-candidate native evidence is claimed here.',
    ):
        assert claim in public_text
    assert '<table' in source and '<caption>' in source
    assert source.count('scope="col"') == 6
    assert 'class="table-container"' in source
    svg = ET.fromstring(re.search(r'<svg\b.*?</svg>', source, re.S)[0])
    assert len(svg.findall('.//*[@data-node]')) == 4
    assert len(svg.findall('.//*[@marker-end]')) == 3


def assert_named_test_anchor(contents, function_name, fragment):
    tree = ast.parse(contents)
    functions = [node for node in tree.body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and node.name == function_name]
    assert len(functions) == 1, function_name
    match = re.fullmatch(r'L(\d+)-L(\d+)', fragment)
    assert match, fragment
    first, last = map(int, match.groups())
    function = functions[0]
    assert first == function.lineno and first <= last <= function.end_lineno


def test_named_test_anchor_rejects_neighboring_function():
    contents = 'def test_first():\n    pass\n\ndef test_second():\n    pass\n'
    assert_named_test_anchor(contents, 'test_first', 'L1-L2')
    with pytest.raises(AssertionError):
        assert_named_test_anchor(contents, 'test_first', 'L4-L5')
    with pytest.raises(AssertionError):
        assert_named_test_anchor(contents, 'test_missing', 'L1-L2')


@pytest.mark.parametrize('name', tuple(
    name for name in DELIVERED_PAGES if name == 'claim-traceability.html'
))
def test_traceability_rows_and_literal_test_nodeids(name):
    source = read(name)
    rows = re.findall(r'<tr data-invariant="([^"]+)">(.*?)</tr>', source, re.S)
    assert [key for key, _ in rows] == [
        'snapshot', 'ownership', 'quarantine', 'restore-order', 'commit',
        'crash-resume', 'empty-app', 'historical-fallback', 'path-drift',
        'path-consent', 'config-rollback', 'state-consent', 'guest-timeout',
        'host-watchdog', 'extraction-diagnostics', 'proof-scope',
        'cache-authority', 'deadline', 'platform-streams',
    ]
    for key, row in rows:
        assert 'class="implementation"' in row, key
        assert 'data-test-node=' in row or 'data-gap="pending"' in row, key
        assert 'REFERENCE ONLY' in row or 'PENDING' in row, key
    references = [(attrs, content) for attrs, content in re.findall(
        r'<a\b([^>]*data-test-node="[^"]+"[^>]*)>(.*?)</a>', source, re.S)]
    assert len(references) >= 13
    for attrs, content in references:
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', attrs))
        nodeid = attrs['data-test-node']
        path, function_name = nodeid.split('::')
        assert path.startswith('tests/') and function_name.startswith('test_')
        assert f'<code>{nodeid}</code>' in content
        linked, fragment = source_reference(attrs['href'])
        assert linked == (REPOSITORY / path).resolve()
        assert_named_test_anchor(linked.read_text(encoding='utf-8'), function_name, fragment)
    public_text = ' '.join(Page(source).texts)
    for claim in (
        'This atlas checks reference existence and structure, not the behavior of the referenced tests.',
        'This page links available tests; it embeds no execution result. Consult candidate-bound verification records; availability is not proof.',
        'Source-observed concern, not a runtime-reproduced defect: extraction diagnostics may be overwritten by the outer failure record; provenance-write failure may replace the primary message.',
        'No native-current execution receipt is supplied; all current native claims remain PENDING.',
        'No dedicated behavior test is linked for crash resume or the empty-APP early return.',
        'Historical harness-initiated restoration is not current Pascal rollback proof.',
    ):
        assert claim in public_text


@pytest.mark.parametrize('name', tuple(
    name for name in DELIVERED_PAGES if name == 'harness-failures.html'
))
def test_harness_failures_budgets_responsibility_and_evidence(name):
    source = read(name)
    rows = re.findall(r'<tr data-fault="([^"]+)">(.*?)</tr>', source, re.S)
    assert [key for key, _ in rows] == [
        'guest-timeout', 'scenario-artifact', 'restore-attach', 'guest-not-off',
        'extraction', 'incomplete-evidence', 'verification', 'cleanup',
    ]
    for key, row in rows:
        assert row.count('<td>') == 4, key
        assert 'scope="row"' in row and '<a href=' in row, key
        assert 'PENDING' in row, key
    public_text = ' '.join(Page(source).texts)
    for claim in (
        'Guest runner budget: 300 seconds by default; bounded kill/waits can return 124. Kill failure throws instead.',
        'Host Off watchdog: independent 600-second default. These budgets are not added into one shared deadline.',
        'Generic bootstrap rejects any nonzero runner exit, attempts failed records, and leaves the guest up without controlled shutdown.',
        'The host does not automatically Stop-VM on watchdog failure and does not directly propagate guest exit 124 as its own exit code.',
        'A scenario-specific runner may interpret an expected step failure and return 0 with expected artifacts; generic bootstrap does not interpret legacy expectFailure.',
        'Failure extraction attempts evidence-disk detach, then read-only mount and copy. It may succeed or fail while the guest is running.',
        'Standalone verifier host provenance is optional; the orchestrator requires and passes host provenance.',
        'Partial evidence, missing done.json, malformed/nonzero completion or hash mismatch cannot certify controlled success.',
        'Source-observed diagnostic-loss concern, not reproduced or fixed here: extraction writes host-failure.json, then the outer catch can overwrite that same file; provenance-write failure can replace the primary message.',
        'Finally attempts both disk detaches and both image dismounts independently; it does not delete VM, checkpoint, VHDX or archive.',
        'Historical MAX_PATH recovery and verifier success do not rewrite failed host overall status or bind a new candidate.',
        'REFERENCE ONLY: available tests and source links embed no execution result. Native current remains PENDING.',
    ):
        assert claim in public_text
    assert '<code>300</code>' not in source  # budgets must remain translated human text
    svg = ET.fromstring(re.search(r'<svg\b.*?</svg>', source, re.S)[0])
    assert len(svg.findall('.//*[@data-node]')) == 6
    assert len(svg.findall('.//*[@marker-end]')) == 5
    for attrs, content in re.findall(r'<a\b([^>]*data-test-node="[^"]+"[^>]*)>(.*?)</a>', source, re.S):
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', attrs))
        nodeid = attrs['data-test-node']
        path, function_name = nodeid.split('::')
        linked, fragment = source_reference(attrs['href'])
        assert linked == (REPOSITORY / path).resolve()
        assert f'<code>{nodeid}</code>' in content
        assert_named_test_anchor(linked.read_text(encoding='utf-8'), function_name, fragment)


@pytest.mark.parametrize('name', (
    'installer-states.html', 'resource-ownership.html',
    'claim-traceability.html', 'harness-failures.html',
))
def test_responsibility_tables_have_named_keyboard_regions(name):
    source = read(name)
    page = Page(source)
    regions = [attrs for _, attrs in page.elements
               if attrs.get('class') == 'table-container']
    assert regions, name
    for attrs in regions:
        assert attrs.get('role') == 'region', name
        assert attrs.get('tabindex') == '0', name
        label = attrs.get('aria-label')
        assert label, name
        assert attrs.get('data-i18n-label') == label, name
        assert translations(source)[label].strip(), name


def test_all_sources_share_one_full_published_revision():
    revisions = set()
    for name in ('index.html', *DELIVERED_PAGES):
        for href in Page(read(name)).links:
            if urlsplit(href).scheme:
                source_reference(href)
                revisions.add(urlsplit(href).path.split('/')[4])
    assert len(revisions) == 1
    assert re.fullmatch(r'[0-9a-f]{40}', revisions.pop())


LIGHT_PALETTE = {
    'paper': '#f5f5f5', 'paper-2': '#ececec', 'surface': '#fff',
    'ink': '#2d3142', 'muted': '#4f5d75', 'soft': '#5a6580',
    'rule-solid': '#bfc0c0', 'accent': '#bf4520', 'link': '#2e5aa8',
}
DARK_PALETTE = {
    'paper': '#2d3142', 'paper-2': '#393e53', 'surface': '#393e53',
    'ink': '#f5f5f5', 'muted': '#bfc0c0', 'soft': '#bfc0c0',
    'rule-solid': 'rgba(191,192,192,0.25)', 'accent': '#f08a59', 'link': '#8ab4ef',
}


def resolve_paint(value, palette):
    match = re.fullmatch(r'var\(--([\w-]+)\)', value)
    assert match, value
    return palette[match[1]]


def theme_palette(source, dark=False):
    selector = r':root\[data-theme="dark"\]' if dark else ':root'
    match = re.search(selector + r'\s*\{([^}]+)\}', source)
    assert match, 'theme palette required'
    return dict(re.findall(r'--([\w-]+):\s*([^;]+);', match[1]))


@pytest.mark.parametrize('name', ('index.html', *DELIVERED_PAGES))
def test_theme_controls_and_complete_semantic_paint(name):
    source = read(name)
    page = Page(source)
    theme_buttons = [attrs for attrs in page.buttons if attrs.get('id') == 'theme-toggle']
    assert len(theme_buttons) == 1
    button = theme_buttons[0]
    assert 'hidden' in button and button['type'] == 'button'
    assert button['aria-pressed'] == 'false'
    assert button['aria-label'] == button['title'] == 'Switch to dark theme'
    assert 'class="control-bar"' in source
    assert 'data-theme' not in re.search(r'<html\b[^>]*>', source)[0]
    assert source.index('id="language-controls"') < source.index('id="theme-toggle"')
    for required in ('min-width:44px', 'min-height:44px', '.theme-moon', '.theme-sun',
                     'Switch to dark theme', 'Switch to light theme',
                     'Activar tema oscuro', 'Activar tema claro'):
        assert required in source
    for dark, expected in ((False, LIGHT_PALETTE), (True, DARK_PALETTE)):
        assert theme_palette(source, dark) == expected
    styles = re.search(r'<style>(.*?)</style>', source, re.S)[1]
    for rule in re.findall(r'([^{}]+)\{([^{}]*)\}', styles):
        if '--paper:' not in rule[1]:
            assert not re.search(r'#[0-9a-fA-F]{3,8}\b', rule[1]), rule
    assert 'box-shadow' not in styles and 'animation:' not in styles
    if name != 'index.html':
        svg = ET.fromstring(re.search(r'<svg\b.*?</svg>', source, re.S)[0])
        for element in svg.iter():
            for paint in ('fill', 'stroke'):
                value = element.attrib.get(paint)
                if value and value != 'none':
                    match = re.fullmatch(r'var\(--([\w-]+)\)', value)
                    assert match, (element.tag, paint, value)
                    assert match[1] in LIGHT_PALETTE
        background = svg.find('{http://www.w3.org/2000/svg}rect')
        assert background.attrib['fill'] == 'var(--paper)'


def contrast_ratio(first, second):
    def luminance(color):
        color = color.lstrip('#')
        if len(color) == 3:
            color = ''.join(character * 2 for character in color)
        channels = [int(color[index:index + 2], 16) / 255 for index in (0, 2, 4)]
        linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
                  for value in channels]
        return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
    bright, dim = sorted((luminance(first), luminance(second)), reverse=True)
    return (bright + 0.05) / (dim + 0.05)


@pytest.mark.parametrize('name', ('index.html', *DELIVERED_PAGES))
def test_theme_text_and_essential_mark_contrast(name):
    for dark in (False, True):
        palette = theme_palette(read(name), dark)
        for surface in ('paper', 'paper-2', 'surface'):
            for text in ('ink', 'muted', 'soft', 'link'):
                assert contrast_ratio(palette[text], palette[surface]) >= 4.5, (dark, text, surface)
            assert contrast_ratio(palette['accent'], palette[surface]) >= 3


THEME_DOM_HARNESS = r"""
const vm = require('node:vm');
const fs = require('node:fs');
const script = fs.readFileSync(0, 'utf8');
function run(saved, blocked = false) {
  const storage = {...saved};
  const makeButton = language => ({dataset: {language}, attributes: {}, hidden: true,
    events: {}, setAttribute(k, v) { this.attributes[k] = v; },
    addEventListener(k, v) { this.events[k] = v; }});
  const es = makeButton('es'), en = makeButton('en'), theme = makeButton();
  const controls = {hidden: true, querySelectorAll: () => [es, en]};
  const label = {dataset: {i18nLabel: 'Language'}, setAttribute() {}};
  const node = {textContent: 'Product', parentElement: {closest: () => false}};
  let visited = false;
  const root = {lang: 'en', dataset: {}};
  const context = {NodeFilter: {SHOW_TEXT: 4}, document: {
    documentElement: root,
    createTreeWalker: () => ({currentNode: node, nextNode: () => {
      if (visited) return false; visited = true; return true;
    }}),
    getElementById: id => id === 'language-controls' ? controls : theme,
    querySelectorAll: () => [label],
  }, localStorage: {
    getItem(key) { if (blocked) throw Error('blocked'); return storage[key] ?? null; },
    setItem(key, value) { if (blocked) throw Error('blocked'); storage[key] = value; },
  }};
  vm.runInNewContext(script, context);
  const state = () => ({theme: root.dataset.theme, language: root.lang,
    label: theme.attributes['aria-label'], title: theme.title,
    pressed: theme.attributes['aria-pressed'], hidden: theme.hidden,
    text: node.textContent, storage: {...storage}});
  const initial = state();
  theme.events.click();
  const toggled = state();
  en.events.click();
  const english = state();
  theme.events.click();
  const restored = state();
  return {initial, toggled, english, restored};
}
const cases = [run({}), run({'yasb-limitora-theme': 'dark', 'yasb-limitora-language': 'en'}),
  run({'yasb-limitora-theme': 'invalid', 'yasb-limitora-language': 'es'}), run({}, true),
  run({'yasb-limitora-theme': 'light', 'yasb-limitora-language': 'en'})];
const reload = run(cases[0].english.storage).initial;
process.stdout.write(JSON.stringify({cases, reload}));
"""


@pytest.mark.parametrize('name', ('index.html', *DELIVERED_PAGES))
def test_theme_controller_live_persistence_storage_and_language_preservation(name):
    # Optional JS tool only: never install it or gate structural/color checks on it.
    node = shutil.which('node')
    if node is None:
        pytest.skip('Optional atlas JS execution unavailable: Node not found; structural/color checks remain active.')
    source = read(name)
    script = re.search(r'<script>(.*?)</script>', source, re.S)[1]
    result = subprocess.run([node, '-e', THEME_DOM_HARNESS], input=script,
                            text=True, encoding='utf-8', capture_output=True, check=False,
                            timeout=10)
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    for index, case in enumerate(observed['cases']):
        for state in case.values():
            dark = state['theme'] == 'dark'
            assert state['pressed'] == str(dark).lower()
            expected = (('Activar tema claro' if dark else 'Activar tema oscuro')
                        if state['language'] == 'es' else
                        ('Switch to light theme' if dark else 'Switch to dark theme'))
            assert state['label'] == state['title'] == expected
        initial_dark = index == 1
        assert case['initial']['theme'] == ('dark' if initial_dark else 'light')
        assert case['initial']['hidden'] is False
        assert case['initial']['pressed'] == str(initial_dark).lower()
        assert case['initial']['label'] == case['initial']['title']
        assert case['toggled']['theme'] == ('light' if initial_dark else 'dark')
        assert case['toggled']['language'] == case['initial']['language']
        assert case['toggled']['text'] == case['initial']['text']
        assert case['english']['language'] == 'en' and case['english']['text'] == 'Product'
        assert case['english']['theme'] == case['toggled']['theme']
        assert case['english']['label'] == ('Switch to dark theme' if initial_dark else 'Switch to light theme')
        assert case['english']['title'] == case['english']['label']
        assert case['restored']['theme'] == case['initial']['theme']
        assert case['restored']['language'] == 'en'
        if index != 3:
            assert case['toggled']['storage']['yasb-limitora-theme'] == case['toggled']['theme']
            assert case['english']['storage']['yasb-limitora-language'] == 'en'
    assert observed['cases'][2]['initial']['storage']['yasb-limitora-theme'] == 'invalid'
    assert observed['cases'][3]['restored']['storage'] == {}
    assert observed['cases'][0]['initial']['label'] == 'Activar tema oscuro'
    assert observed['cases'][0]['toggled']['label'] == 'Activar tema claro'
    assert observed['reload']['theme'] == 'dark' and observed['reload']['language'] == 'en'


PROOF_CLAIMS = {
    'proof-harness.html': (
        'Generic transport success is not installer lifecycle proof.',
        'This is not hostile-guest protection or cryptographic attestation.',
        'Bootstrap failure leaves the guest running;',
        'Never run the installer or uninstaller on the host.',
    ),
    'proof-cases.html': (
        'The uninstaller hash was observed, not pre-pinned.',
        'These historical bytes do not establish proof of the current candidate.',
        'C4 supplies a runner and real child-process boundary tests, but not the complete native scenario and required modules.',
        'not an observation of zero dialogs.',
        'Recovered verifier success does not rewrite that failed orchestration',
    ),
    'lifecycle-verify.html': (
        'normal CLI execution does not rebuild, reinstall or launch a VM.',
        'It is not part of installed CLI startup.',
        'Historical C5 evidence does not certify new candidate bytes;',
        'no tag, installer artifact or release is published in that record.',
    ),
}


@pytest.mark.parametrize('name', tuple(name for name in DELIVERED_PAGES if name in PROOF_CLAIMS))
def test_named_proof_claims(name):
    public_text = ' '.join(Page(read(name)).texts)
    for claim in PROOF_CLAIMS[name]:
        assert claim in public_text
    if name == 'proof-cases.html':
        public_source = read(name).split('<script>')[0]
        for technical in (
            'yasb-limitora-0.2.0-setup.exe', '11,054,574',
            '1d58f3618f5b22ddccacc7be2dcf8e3a1e9a90dba57dffe431d8ca8ae6df3394',
            '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART',
            'dialogAnswerAttempted=false', 'overall=failed',
        ):
            assert f'<code>{technical}</code>' in public_source
    if name == 'lifecycle-verify.html':
        svg = ET.fromstring(re.search(r'<svg\b.*?</svg>', read(name), re.S)[0])
        edges = {(edge.attrib['data-from'], edge.attrib['data-to'])
                 for edge in svg.findall('{http://www.w3.org/2000/svg}path')}
        assert edges == {
            ('source', 'frozen'), ('frozen', 'candidate'), ('candidate', 'install'),
            ('install', 'cli'), ('cli', 'boundary'), ('candidate', 'vm'),
            ('vm', 'evidence'), ('evidence', 'verifier'),
        }
