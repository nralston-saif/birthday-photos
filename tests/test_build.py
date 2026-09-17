import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'build'))
from build_page import collect_data, render_page, validate_data
ROOT=Path(__file__).resolve().parents[1]

class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.data,cls.assets=collect_data(ROOT/'work',ROOT/'your-writing')
    def test_every_asset_exists(self):
        self.assertEqual(len(self.assets),128)
        for asset,path in self.assets.items(): self.assertTrue(path.is_file(),asset)
    def test_build_does_not_need_the_local_work_folder(self):
        data, assets = collect_data(ROOT/'missing-work-directory',ROOT/'your-writing')
        self.assertEqual(data,self.data)
        for path in assets.values(): self.assertTrue(path.is_relative_to(ROOT/'assets'))
    def test_unknown_assignment_fails_build(self):
        data=copy.deepcopy(self.data);data['edits']['photos']['IMG_0147.HEIC']['waypoint']='missing'
        with self.assertRaisesRegex(ValueError,'Unknown place'): validate_data(data)
    def test_writing_cannot_break_out_of_script(self):
        data=copy.deepcopy(self.data);data['meta']['dedication']='</script><img src=x onerror=alert(1)>'
        page=render_page(data)
        self.assertNotIn('</script><img',page)
        self.assertIn('\\u003c/script>',page)
    def test_complete_html_without_remote_dependencies(self):
        page=render_page(self.data)
        self.assertIn('name="viewport"',page)
        self.assertIn('Happy Birthday Dad!',page)
        self.assertNotIn('window.claude',page)
        self.assertNotIn('fonts.googleapis.com',page)
        self.assertNotIn('/*__',page)
    def test_published_map_dependencies_are_self_hosted(self):
        import re
        published=ROOT/'site/publish'
        html=(published/'index.html').read_text()
        references=re.findall(r'(?:src|href)="(vendor/[^"\s]+)"',html)
        self.assertEqual(set(references),{'vendor/leaflet/leaflet.js','vendor/leaflet/leaflet.css'})
        for ref in references: self.assertTrue((published/ref).is_file(),ref)
        css=(published/'vendor/leaflet/leaflet.css').read_text()
        for image in re.findall(r'url\((images/[^)]+)\)',css):
            self.assertTrue((published/'vendor/leaflet'/image).is_file(),image)
        self.assertTrue((published/'vendor/leaflet/LICENSE').is_file())

if __name__=='__main__':unittest.main()
