"""Progressive, offline atlas contracts; these are not native UI proofs."""
import json
import os
import re
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
    'proof-cases.html', 'lifecycle-verify.html',
)
# Registration is deliberate: a missing registered file is always an error.
DELIVERED_PAGES = (
    'purpose.html', 'structure.html', 'data-journey.html', 'installer-transaction.html',
    'setup-assist.html', 'proof-harness.html', 'proof-cases.html', 'lifecycle-verify.html',
)
GROUPS = {
    'product': COMPLETE_ORDER[:3],
    'installer': COMPLETE_ORDER[3:7],
    'combined': COMPLETE_ORDER[7:],
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
    assert {b['data-language'] for b in page.buttons} == {'es', 'en'}
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
    assert not re.search(r'<link\b|@import|(?:src|href)="https?://', source)
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
    for href in Page(read(name)).links:
        target = urlsplit(href)
        assert not (target.scheme or target.netloc), href
        linked = ((ROOT / unquote(target.path)) if target.path else ROOT / name).resolve()
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
        if relative.startswith('src/'):
            assert target.path.startswith('../../src/'), href


@pytest.mark.parametrize('name', ('index.html', *DELIVERED_PAGES))
def test_sections_and_filled_dot_markers(name):
    source = read(name)
    marker = re.search(r'\.section-nav a::before\{([^}]+)\}', source)[1]
    assert 'border-radius:50%' in marker
    assert 'background:#4f5d75' in marker
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
    assert f'Available: {len(DELIVERED_PAGES)} / Planned: 8' in source


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
    assert 'The diagram-only HTTP server does not serve source files.' in ' '.join(Page(source).texts)
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
        target = (REPOSITORY / repository_path).resolve()
        relocated = Path(os.path.relpath(target, ROOT)).as_posix()
        assert f'href="{relocated}#{fragment}"' in source


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
        target = (REPOSITORY / 'src' / 'yasb_limitora' / filename).resolve()
        relocated = Path(os.path.relpath(target, ROOT)).as_posix()
        assert f'href="{relocated}#{fragment}"' in source


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
        target = (REPOSITORY / repository_path).resolve()
        relocated = Path(os.path.relpath(target, ROOT)).as_posix()
        assert f'href="{relocated}#{fragment}"' in source


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
    target = (REPOSITORY / 'packaging/inno/yasb-limitora.iss').resolve()
    relocated = Path(os.path.relpath(target, ROOT)).as_posix()
    for fragment in ('L1-L45', 'L222-L448', 'L904-L952'):
        assert f'href="{relocated}#{fragment}"' in source


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
        target = (REPOSITORY / repository_path).resolve()
        relocated = Path(os.path.relpath(target, ROOT)).as_posix()
        for fragment in fragments:
            assert f'href="{relocated}#{fragment}"' in source


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
        target = (REPOSITORY / repository_path).resolve()
        relocated = Path(os.path.relpath(target, ROOT)).as_posix()
        for fragment in fragments:
            assert f'href="{relocated}#{fragment}"' in source


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
        target = (REPOSITORY / repository_path).resolve()
        relocated = Path(os.path.relpath(target, ROOT)).as_posix()
        for fragment in fragments:
            assert f'href="{relocated}#{fragment}"' in source


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
        target = (REPOSITORY / repository_path).resolve()
        relocated = Path(os.path.relpath(target, ROOT)).as_posix()
        for fragment in fragments:
            assert f'href="{relocated}#{fragment}"' in source


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
