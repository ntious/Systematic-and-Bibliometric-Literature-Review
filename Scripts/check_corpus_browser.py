"""Isolated synthetic end-to-end check of corpus totals and dated venue metrics."""
import argparse
import base64
import csv
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import zipfile

from playwright.sync_api import sync_playwright, expect
from slr.dashboard import DashboardServer, Workspace


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='outputs/corpus-browser-qa')
    output=Path(parser.parse_args().output).resolve();output.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory(prefix='slr-corpus-browser-') as tmp:
        workspace=Workspace(Path(tmp)/'workspace')
        entry=workspace.create({'name':'Synthetic corpus analytics QA','question':'Synthetic demonstration only','criteria':'No research decisions','reviewers':['A','B'],'adjudicator':'C'})
        workspace.import_uploads(entry['id'],{'source':'Synthetic fixture','files':[{'name':'fixture.json','base64':base64.b64encode(Path('Examples/corpus_records.json').read_bytes()).decode()}]})
        server=DashboardServer(('127.0.0.1',0),workspace)
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        errors=[]
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
                page=browser.new_page(viewport={'width':1440,'height':1100},reduced_motion='reduce',accept_downloads=True)
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{server.server_port}/#analytics?review='+entry['id'])
                page.get_by_role('heading',name='Top publication venues',exact=True).wait_for()
                assert page.locator('.corpus-metrics .metric').count()==8
                assert page.locator('.corpus-metrics .metric').first.locator('.metric-value').inner_text()=='3'
                assert 'No external metrics saved' in page.locator('#main').inner_text()
                page.locator('#analysis-scope').select_option('included')
                expect(page.locator('.corpus-metrics .metric-value').first).to_have_text('0')
                page.locator('#analysis-scope').select_option('all')
                page.get_by_role('heading',name='Top publication venues',exact=True).wait_for()
                page.get_by_role('button',name='Import venue metrics',exact=True).click()
                page.locator('[name="metrics"]').set_input_files('Examples/synthetic_venue_metrics.csv')
                page.get_by_role('button',name='Import metric snapshot',exact=True).click()
                page.get_by_text('Ambiguous metric rows — choose a category',exact=True).wait_for()
                page.locator('#metric-category').select_option('Computing')
                expect(page.locator('.corpus-venue-table tbody tr').first.locator('td').nth(3)).to_have_text('5.1')
                assert 'Fictional provider - SYNTHETIC EXAMPLE' in page.locator('#main').inner_text()
                assert page.locator('.corpus-venue-table tbody tr').first.locator('td').nth(3).inner_text()=='5.1'
                page.locator('#metric-year').select_option('2024')
                expect(page.locator('.corpus-venue-table tbody tr').first.locator('td').nth(3)).to_have_text('4.5')
                page.locator('#metric-year').select_option('2025')
                expect(page.locator('.corpus-venue-table tbody tr').first.locator('td').nth(3)).to_have_text('5.1')
                page.locator('#venue-search').fill('Journal B')
                assert page.locator('.corpus-venue-table tbody tr').count()==1
                assert page.locator('.corpus-venue-table tbody tr td').nth(3).inner_text()=='*'
                page.locator('#venue-search').fill('')
                with page.expect_download() as download:
                    page.get_by_role('button',name='Export analysis',exact=True).click()
                archive=output/'corpus-analysis.zip';download.value.save_as(archive)
                with zipfile.ZipFile(archive) as z:
                    rows=list(csv.DictReader(io.StringIO(z.read('publication-venues.csv').decode())))
                    assert len(rows)==2 and rows[0]['TP']=='2' and rows[0]['year']=='2025'
                    assert rows[1]['citescore']=='*'
                page.get_by_role('button',name='Import SCImago',exact=True).click()
                page.locator('[name="year"]').fill('2024')
                page.locator('[name="retrieved"]').fill('2026-10-22')
                page.locator('[name="metrics"]').set_input_files({'name':'scimago.csv','mimeType':'text/csv','buffer':b'Rank;Title;Issn;SJR;SJR Best Quartile;H index;Publisher;Categories\n1;Example Journal A;12345679;"1,25";Q1;42;Example Press;Computing (Q1)\n'})
                page.get_by_role('button',name='Import SCImago data',exact=True).click()
                expect(page.locator('.corpus-venue-table tbody tr').first.locator('td').nth(5)).to_have_text('1.25')
                expect(page.locator('.corpus-venue-table tbody tr').first.locator('td').nth(6)).to_contain_text('SJR')
                expect(page.get_by_role('heading',name='Metric sources',exact=True)).to_be_visible()
                expect(page.locator('#analytics-content a[href="https://www.scimagojr.com/journalrank.php"]')).to_be_visible()
                with page.expect_download() as download:
                    page.get_by_role('button',name='Export analysis',exact=True).click()
                archive=output/'scimago-analysis.zip';download.value.save_as(archive)
                with zipfile.ZipFile(archive) as z:
                    assert 'scimago-original.csv' in z.namelist()
                    assert b'SCImago Journal & Country Rank' in z.read('metric-sources.md')
                page.get_by_role('button',name='Fetch online',exact=True).click()
                expect(page.locator('[name="provider"]')).to_be_visible()
                page.get_by_role('button',name='Cancel',exact=True).click()
                page.screenshot(path=str(output/'analytics-desktop.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('() => document.documentElement.scrollWidth<=innerWidth'), 'Mobile page overflow'
                page.screenshot(path=str(output/'analytics-mobile.png'),full_page=True)
                assert not errors,errors
                browser.close()
        finally:
            server.shutdown();server.server_close();thread.join(5);workspace.executor.shutdown(wait=True)
    print('Corpus browser QA passed: eight totals, scope, snapshot import, ambiguity/category/year, venue search, NA values, ZIP export and mobile layout.')


if __name__=='__main__':main()
