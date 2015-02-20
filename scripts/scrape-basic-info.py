#!/usr/bin/env python
import requests
import lxml.html
import pandas as pd
import namestand
import sys
import re
import itertools
flatten = lambda x: list(itertools.chain.from_iterable(x))

agencies = pd.read_csv("data/agency-list.csv")
ids = agencies[["Operation/Caregiver Name", "Facility ID"]].values

URL_TEMPLATE = "http://www.dfps.state.tx.us/Child_Care/Search_Texas_Child_Care/ppFacilityDetails.asp?ptype=RC&fid={facility_id}"

num_pattern = re.compile(r"^\d+$")
defic_pattern = re.compile(r"^(\d+) w\w+ weighted as (.*)$")
whitespace_pattern = re.compile(r"\s+")

def try_int_convert(string):
    if re.match(num_pattern, string):
        return int(string)
    else: return string

def scrape_facility(name, facility_id):
    url = URL_TEMPLATE.format(facility_id=facility_id)
    sys.stderr.write("{0}\n".format(url))
    html = requests.get(url).content
    dom = lxml.html.fromstring(html)
    sections = dom.cssselect("form[name='frm_ppFacilityDetails'] > table > tr")
    overview = sections[0]
    rows = overview.cssselect("table > tr")[1:-1]
    kv = [ [ cell.text_content().strip() 
        for cell in r.cssselect("td") ] 
            for r in rows ]
    overview_dict = dict((namestand.downscore(x[0]), try_int_convert(re.sub(whitespace_pattern, " ", x[1]))) for x in kv)
    inspection_section = sections[2]
    inspection_rows = inspection_section.cssselect("table > tr")[:4]
    inspection_dict = dict(("n_" + namestand.downscore(r.cssselect("td")[1].text), int(r.cssselect("td a")[0].text_content()))
        for r in inspection_rows)
    standards_section = sections[-4]
    standards_dict = { "n_standards": re.search(r"(\d+) standards were", standards_section.text_content()).group(1) }
    defic_section = sections[-1]
    defic_rows = defic_section.cssselect("table > tr")[:5]
    defic_texts = (re.sub(whitespace_pattern, " ", d.text_content().strip()) for d in defic_rows)
    defic_matches = (re.match(defic_pattern, t).groups() for t in defic_texts)
    defic_dict = dict(("n_defic_" + namestand.downscore(m[1]), int(m[0])) for m in defic_matches)
    combined = dict(flatten(d.items() for d in (overview_dict, inspection_dict, standards_dict, defic_dict)))
    combined["facility_id"] = facility_id
    return combined

def scrape_all():
    dicts = [ scrape_facility(*tup) for tup in ids ]
    df = pd.DataFrame(dicts)
    return df

if __name__ == "__main__":
    df = scrape_all()
    df.to_csv(sys.stdout, index=False, encoding="utf-8")

