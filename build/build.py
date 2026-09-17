#!/usr/bin/env python3
"""One-command, offline build. Never uploads or publishes anything."""
import argparse
import json
import shutil
import tempfile
from pathlib import Path
from build_page import collect_data, collect_scanned_data, render_page

ROOT = Path(__file__).resolve().parent.parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--writing',type=Path,help='Import a writing JSON export, validate it, and save it to your-writing before building.')
    parser.add_argument('--refresh-media', action='store_true', help='Update the tracked catalog and web assets from the local work folder after processing new photos.')
    args=parser.parse_args()
    writing=ROOT/'your-writing'
    with tempfile.TemporaryDirectory(prefix='birthday-atlas-build-') as tmp:
        temp=Path(tmp)
        authored=temp/'writing';shutil.copytree(writing,authored)
        if args.writing:
            overlay=json.loads(args.writing.expanduser().read_text())
            for section in ('meta','waypoints','photos','places'):
                if not isinstance(overlay.get(section,{}),dict): raise ValueError('Invalid '+section+' section')
                path=authored/(section+'.json');current=json.loads(path.read_text())
                for key,value in overlay.get(section,{}).items():
                    if section=='meta': current[key]=value
                    else: current[key]={**current.get(key,{}),**value}
                path.write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n')
        collector = collect_scanned_data if args.refresh_media else collect_data
        data,assets=collector(ROOT/'work',authored)
        publish=temp/'publish';publish.mkdir()
        for rel,src in assets.items():
            target=publish/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target)
        html=render_page(data);(publish/'index.html').write_text(html)
        gaz=(ROOT/'build/gazetteer.txt').read_text()
        (publish/'gazetteer.js').write_text('window.__GAZ='+json.dumps(gaz,ensure_ascii=True)+';\n')
        (publish/'vercel.json').write_text(json.dumps({'framework':None,'buildCommand':None,'outputDirectory':'.','headers':[{'source':'/(.*)','headers':[{'key':'X-Robots-Tag','value':'noindex, nofollow'},{'key':'X-Content-Type-Options','value':'nosniff'},{'key':'Referrer-Policy','value':'same-origin'}]}]},indent=2)+'\n')
        (publish/'robots.txt').write_text('User-agent: *\nDisallow: /\n')
        (publish/'credits.txt').write_text('Map data: OpenStreetMap contributors, https://www.openstreetmap.org/copyright\nPlace search: GeoNames, https://www.geonames.org/ (CC BY 4.0).\nFamily photographs and writing: private family collection.\n')
        # All validation finishes before replacing the publishable output.
        output=ROOT/'site/publish';output.mkdir(parents=True,exist_ok=True)
        for src in publish.rglob('*'):
            if src.is_file():
                dest=output/src.relative_to(publish);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
        (ROOT/'site/chart.html').write_text(html)
        if args.refresh_media:
            for relative, source in assets.items():
                target=ROOT/'assets'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
            catalog={key:data[key] for key in ('photos','panels','waypoints','unplaced')}
            (ROOT/'content').mkdir(exist_ok=True)
            (ROOT/'content/catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
        if args.writing:
            for section in ('meta','waypoints','photos','places'):
                shutil.copy2(authored/(section+'.json'),writing/(section+'.json'))
        (ROOT/'site/publish_manifest.json').write_text(json.dumps({'version':data['version'],'photos':len(data['photos']),'journeyStops':len(data['journey']['stops']),'assets':sorted(str(f.relative_to(publish)) for f in publish.rglob('*') if f.is_file())},indent=2)+'\n')
        print('Built site/publish: %d photographs, %d places, %d journey stops.' % (len(data['photos']),len(data['waypoints'])+len(data['edits']['places']),len(data['journey']['stops'])))
        print('All images and writing validated. Preview: python3 -m http.server 8777 --bind 127.0.0.1 --directory site/publish')

if __name__=='__main__': main()
