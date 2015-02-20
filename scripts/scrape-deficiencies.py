#!/usr/bin/env python
import requests
import lxml.html
import re
import ast
import pandas as pd
import sys, os
import datetime

class Facility(object):
    base_url = "http://www.dfps.state.tx.us/Child_Care/Search_Texas_Child_Care/CCLNET/Source/Provider/ppComplianceHistory.aspx"
    def __init__(self, facility_id):
        self.facility_id = facility_id
    
    def get_compliance_url(self):
        tmpl = self.base_url + "?fid={facility_id}&tab=2"
        return tmpl.format(facility_id=self.facility_id)
    
    def get_params(self, dom):
        form = dom.cssselect("#aspnetForm")[0]
        params = dict((i.attrib["name"], i.value) for i in form.cssselect("input") if "name" in i.attrib)
        params["__CALLBACKID"] = "ctl00$contentBase$tabSections$gridSummary"
        return params

    def parse_deficiency_callback(self, text):
        obj = ast.literal_eval(re.search(r"[^{]+(.+)\)", text).group(1))
        result = obj["result"]
        dom = lxml.html.fromstring("<html><body>" + result + "</body></html>")
        rows = dom.cssselect("tr[id^=ctl00_contentBase_tabSections_gridSummary_DXDataRow]")
        cells = [ row.cssselect("td") for row in rows ]
        parse_date = lambda x: datetime.datetime.strptime(x, "%m/%d/%Y") if "/" in x else None
        data = [ {
            "facility_id": self.facility_id,
            "date": parse_date(date.text_content()),
            "standard": standard.text_content(),
            "risk_level": risk.text_content(),
            "source": source.text_content(),
            "narrative_id": re.search(r"(\d+)", narrative_id.cssselect("a")[0].attrib["onclick"]).group(1),
            "corrected_at_inspection": corrected.text_content(),
            "correction_deadline": parse_date(correction_deadline.text_content()),
            "correction_verified": parse_date(correction_verified.text_content()),
        } for   date, standard, source, risk,
                corrected, correction_deadline,
                correction_verified, narrative_id in rows ]
        return data
    
    def get_deficiencies(self, get_narratives=False):
        url = self.get_compliance_url()
        sys.stderr.write("Getting {0}\n".format(self.facility_id))
        success = False
        while not success:
            try:
                sys.stderr.write(".")
                html = requests.get(url).content
                dom = lxml.html.fromstring(html)
                name_el = dom.cssselect("#ctl00_contentBase_ProviderInfo1_ppProvider_lblOperationName")[0]
                sys.stderr.write("{0}".format(name_el.text_content().strip()))
                params = self.get_params(dom)
                success = True
            except KeyboardInterrupt: exit()
            except: pass
        success = False
        while not success:
            try:
                sys.stderr.write(".")
                params["__CALLBACKPARAM"] = "c3:GB|21;12|PAGERONCLICK4|PN-1;"
                callback = requests.post(url, data=params).content
                rows = self.parse_deficiency_callback(callback)
                success = True
            except KeyboardInterrupt: exit()
            except: pass
        if get_narratives:
            sys.stderr.write("\nGetting narratives\n")
            for row in rows:
                success = False
                while not success:
                    try:
                        params["__CALLBACKPARAM"] = "c0:FB|1;0;GB|26;12|CUSTOMVALUES9|{0};".format(row["narrative_id"])
                        sys.stderr.write(".")
                        callback = requests.post(url, data=params).content
                        escaped = re.search(r"FB\|0\|\\'([^\^]+)\^", callback).group(1)
                        narr = escaped.decode("string-escape").decode("string-escape")
                        row["narrative"] = narr
                        success = True
                    except KeyboardInterrupt: exit()
                    except: pass
        sys.stderr.write("\n")
        return rows

def get_deficiencies_for_ids(ids, get_narratives=False):
    facilities = map(Facility, ids)
    deficiencies = [ fac.get_deficiencies(get_narratives=get_narratives) for fac in facilities ]
    df = pd.concat(map(pd.DataFrame, deficiencies)).reset_index(drop=True)
    df["corrected_on_time"] = (
        (df["corrected_at_inspection"] == "Yes") |
        (df["correction_verified"] <= df["correction_deadline"])
    )
    return df

if __name__ == "__main__":
    ids =  pd.read_csv("data/agency-list.csv")["Facility ID"].values
    deficiencies = get_deficiencies_for_ids(ids)
    deficiencies.to_csv(sys.stdout, index=False, encoding="utf-8")
