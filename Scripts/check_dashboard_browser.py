"""Optional end-to-end dashboard QA with an isolated synthetic workspace."""
import argparse
import csv
import io
import json
from pathlib import Path
import tempfile
import threading
import zipfile

from playwright.sync_api import sync_playwright, expect
from slr.dashboard import DashboardServer, Workspace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='outputs/dashboard-qa')
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='slr-dashboard-qa-') as directory:
        workspace = Workspace(directory, demo=True)
        server = DashboardServer(('127.0.0.1', 0), workspace)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        errors = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={'width':1440,'height':1020}, device_scale_factor=1, reduced_motion='reduce')
                page.on('pageerror', lambda error: errors.append(str(error)))
                base = f'http://127.0.0.1:{server.server_port}'
                page.goto(base, wait_until='networkidle')
                expect(page.locator('h1')).to_have_text('Your research, in focus.')
                expect(page.locator('.metric-value').first).to_have_text('72')
                expect(page.locator('#demo-banner')).to_be_visible()
                expect(page.locator('#overview-graph .graph-node').first).to_be_visible()
                page.screenshot(path=str(output/'overview.png'), full_page=True)

                page.locator('a.nav-item').filter(has_text='Study library').click()
                page.locator('#library-search').fill('trust')
                expect(page.locator('tbody tr')).to_have_count(5)
                page.locator('.paper-title').first.click()
                expect(page.locator('.drawer')).to_be_visible()
                page.keyboard.press('Escape')
                expect(page.locator('.drawer')).to_have_count(0)
                page.locator('#library-search').fill('')
                page.locator('[data-action="grid-view"]').click()
                expect(page.locator('.paper-card')).to_have_count(12)
                page.screenshot(path=str(output/'library.png'), full_page=True)

                page.locator('a.nav-item').filter(has_text='Bibliometrics').click()
                expect(page.locator('#network-svg .graph-node').first).to_be_visible()
                page.locator('#network-svg .graph-node').first.click()
                expect(page.locator('#network-detail')).to_contain_text('STRONGEST CONNECTIONS')
                page.locator('[data-action="zoom-in"]').click()
                assert 'scale(1.2)' in page.locator('#graph-world').get_attribute('transform')
                with page.expect_response(lambda r: '/api/networks?' in r.url and 'normalization=none' in r.url):
                    page.locator('#normalization').select_option('none')
                with page.expect_download() as download:
                    page.locator('[data-action="graph-export"]').click()
                graph_path=output/'graph-export.json'
                download.value.save_as(graph_path)
                assert json.loads(graph_path.read_text())['graph']['methods']['normalization']=='none'
                page.evaluate('window.scrollTo(0,0)')
                page.locator('[data-action="zoom-reset"]').click()
                page.screenshot(path=str(output/'network.png'), full_page=True)

                page.locator('a.nav-item').filter(has_text='Screening').click()
                expect(page.locator('.reading-title')).to_be_visible()
                page.locator('[data-mode="conflicts"]').click()
                page.locator('#actor-select').select_option('Riley')
                expect(page.locator('.queue-item')).to_have_count(4)
                page.screenshot(path=str(output/'screening.png'), full_page=True)
                page.locator('[data-action="include"]').click()
                page.locator('#field-reason').fill('The synthetic example meets the population criterion.')
                page.locator('#modal-form button[type="submit"]').click()
                expect(page.locator('.queue-item')).to_have_count(3)

                second=workspace.entries[1]['id']
                page.locator('#review-select').select_option(second)
                page.locator('a.nav-item').filter(has_text='Evidence studio').click()
                expect(page.locator('#evidence-inspector')).to_be_visible()
                expect(page.locator('.source-excerpt mark')).to_be_visible()
                expect(page.locator('#evidence-actor')).to_have_value('Jordan')
                page.screenshot(path=str(output/'evidence.png'), full_page=True)
                page.locator('#review-rationale').fill('Checked the exact synthetic passage and its context.')
                page.locator('#support-confirmed').check()
                page.locator('[data-action="approve-evidence"]').click()
                expect(page.locator('.proposal-item')).to_have_count(5)
                page.locator('[data-evidence-filter="flagged"]').click()
                expect(page.locator('[data-action="approve-evidence"]')).to_be_disabled()
                expect(page.locator('.notice.orange')).to_contain_text('Unsupported proposals cannot be approved')
                with page.expect_download() as bundle:
                    page.locator('[data-action="export"]').click()
                archive_path=output/'review-export.zip'
                bundle.value.save_as(archive_path)
                with zipfile.ZipFile(archive_path) as archive:
                    assert 'screening/prisma.svg' in archive.namelist()
                    assert 'evidence/evidence.csv' in archive.namelist()

                page.keyboard.press('Control+k')
                page.locator('#palette-input').fill('protocol')
                page.locator('[data-palette-go="protocol"]').click()
                expect(page.locator('h1')).to_have_text('A shared direction for your review.')
                page.locator('#theme-toggle').click()
                expect(page.locator('html')).to_have_attribute('data-theme','dark')
                page.screenshot(path=str(output/'dark.png'), full_page=True)
                page.locator('#theme-toggle').click()

                page.locator('#demo-new').click()
                for name,value in [('name','Browser QA review'),('question','How can synthetic examples support learning?'),('criteria','Include empirical studies of learning.'),('reviewer1','A'),('reviewer2','B'),('adjudicator','C')]:
                    page.locator('[name="'+name+'"]').fill(value)
                page.locator('#modal-form button[type="submit"]').click()
                expect(page.locator('#review-select')).to_have_value(workspace.entries[-1]['id'])
                expect(page.locator('#demo-banner')).to_be_hidden()
                page.locator('[data-action="import"]').first.click()
                records=[{'source':'synthetic','source_id':'1','title':'=1+1','authors':['Example A'],'year':2024,'doi':'10.9999/ui-1','abstract':'Synthetic browser-test record.'},
                         {'source':'synthetic','source_id':'2','title':'Another synthetic learning study','authors':['Example B'],'year':2023,'doi':'10.9999/ui-2','abstract':'Synthetic browser-test record.'}]
                page.locator('input[name="files"]').set_input_files({'name':'papers.json','mimeType':'application/json','buffer':json.dumps(records).encode()})
                page.locator('#field-source').fill('Synthetic browser QA')
                page.locator('#modal-form button[type="submit"]').click()
                page.locator('[data-action="list-view"]').click()
                expect(page.locator('tbody tr')).to_have_count(2)
                with page.expect_download() as csv_download:
                    page.locator('[data-action="library-export"]').click()
                csv_path=output/'filtered-studies.csv'
                csv_download.value.save_as(csv_path)
                assert "'=1+1" in [c for row in csv.reader(io.StringIO(csv_path.read_text())) for c in row]
                page.locator('a.nav-item').filter(has_text='Screening').click()
                expect(page.locator('.queue-item')).to_have_count(2)
                page.locator('[data-action="include"]').click()
                expect(page.locator('.queue-item')).to_have_count(1)

                page.set_viewport_size({'width':390,'height':844})
                page.reload(wait_until='networkidle')
                page.locator('#menu-button').click()
                expect(page.locator('#sidebar')).to_have_class('sidebar open')
                page.locator('a.nav-item').filter(has_text='Overview').click()
                expect(page.locator('#sidebar')).to_have_class('sidebar')
                expect(page.locator('h1')).to_have_text('Your research, in focus.')
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                page.screenshot(path=str(output/'mobile.png'), full_page=True)
                if errors:
                    raise AssertionError('Browser errors: '+json.dumps(errors))
                browser.close()
            print('Dashboard browser QA passed: overview, filters, study drawer, network, conflict resolution, independent evidence review, exports, palette, theme, new review/import, screening and mobile layout.')
        finally:
            server.shutdown()
            server.server_close()
            workspace.executor.shutdown(wait=True)
            thread.join(timeout=3)


if __name__=='__main__':
    main()
