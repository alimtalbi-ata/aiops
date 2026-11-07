#!/usr/bin/env python3
"""FS1098 real Chromium validation of Prometheus history chart UI."""
import datetime, json, os, pathlib, sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:17898"
root = pathlib.Path.home()/".local/state/aiops-debian-agent/portal-playwright"
out = root/("fs1098-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
out.mkdir(mode=0o700, parents=True, exist_ok=False)
os.chmod(out,0o700)
report={"status":"FAIL","base":BASE,"matrix":[],"errors":[],"screenshots":[]}
print("FS1098_CAPTURE_DIR="+str(out),flush=True)

try:
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path="/usr/bin/chromium",
                                  args=["--no-sandbox","--disable-dev-shm-usage"])
        try:
            page=browser.new_page(viewport={"width":1440,"height":1000},device_scale_factor=1)
            console_errors=[]; page_errors=[]; failed_requests=[]; http_errors=[]; history_responses=[]
            page.on("pageerror",lambda e:page_errors.append(str(e)[:300]))
            page.on("console",lambda m:console_errors.append({"text":m.text[:250],"location":m.location}) if m.type=="error" else None)
            page.on("requestfailed",lambda r:failed_requests.append({"url":r.url,"failure":r.failure}))
            page.on("response",lambda r:http_errors.append({"url":r.url,"status":r.status}) if r.status>=400 else None)
            page.on("response",lambda r:history_responses.append({"url":r.url,"status":r.status}) if "/api/fs1089/prometheus/history" in r.url else None)

            response=page.goto(BASE+"/explorer/visual",wait_until="domcontentloaded",timeout=25000)
            assert response and response.status==200,("visual HTTP",response.status if response else None)
            page.wait_for_function("""() => {
              const s=document.querySelector('#history-status')?.textContent || '';
              return s.includes('points') && document.querySelectorAll('#history-chart path').length > 0;
            }""",timeout=30000)
            assert page.locator("#history-chart").count()==1
            assert page.locator("#history-legend").count()==1
            assert page.locator("#history-legend > span").count()==5
            assert page.locator("#history-chart path").count()==5
            assert "script-src 'sha256-" in (response.headers.get("content-security-policy") or "")
            assert "style-src 'sha256-" in (response.headers.get("content-security-policy") or "")
            page.screenshot(path=str(out/"history-desktop.png"),full_page=True)
            report["screenshots"].append("history-desktop.png")
            print("FS1098_DESKTOP_INITIAL=PASS",flush=True)

            for metric in ("availability","scrape_duration"):
                for window in ("1h","6h","24h"):
                    # Set both selectors without firing intermediate change events:
                    # the explicit refresh below is the only request for this matrix cell.
                    # Rapid selector changes are tested separately as a race scenario.
                    page.evaluate("""([metric, windowSize]) => {
                      document.querySelector('#history-metric').value = metric;
                      document.querySelector('#history-window').value = windowSize;
                    }""", [metric, window])
                    with page.expect_response(lambda r: "/api/fs1089/prometheus/history" in r.url and ("metric="+metric) in r.url and ("window="+window) in r.url,timeout=25000) as response_info:
                        page.locator("#history-refresh").click()
                    api_response=response_info.value
                    assert api_response.status==200,(metric,window,api_response.status)
                    payload=api_response.json()
                    assert payload.get("metric")==metric and payload.get("window")==window
                    series=payload.get("series")
                    assert isinstance(series,list) and len(series)==5,(metric,window,len(series) if isinstance(series,list) else type(series).__name__)
                    total_points=sum(len(s.get("points",[])) for s in series)
                    assert total_points>0,(metric,window,total_points)
                    # Wait for this render cycle to finish, not for a particular label or
                    # hard-coded series count. Then assert the actual DOM and retain diagnostics.
                    page.wait_for_function("""() => {
                      const button=document.querySelector('#history-refresh');
                      const s=document.querySelector('#history-status')?.textContent || '';
                      return button && !button.disabled &&
                        !s.includes('Chargement des séries historiques…') &&
                        (s.includes('points') || s.includes('Erreur de chargement') ||
                         s.includes('Aucune série'));
                    }""",timeout=30000)
                    status=page.locator("#history-status").inner_text()
                    rendered_series=sum(1 for item in series if item.get("points"))
                    svg_paths=page.locator("#history-chart path").count()
                    legend_items=page.locator("#history-legend > span").count()
                    assert "points" in status,(metric,window,"history UI did not render successfully",status)
                    assert status.endswith(" · "+window),(metric,window,"stale window render",status)
                    assert svg_paths==rendered_series,(metric,window,"svg_paths",svg_paths,"expected",rendered_series,"status",status)
                    assert legend_items==rendered_series,(metric,window,"legend_items",legend_items,"expected",rendered_series,"status",status)
                    report["matrix"].append({"metric":metric,"window":window,"status":api_response.status,
                                              "series":len(series),"rendered_series":rendered_series,
                                              "svg_paths":svg_paths,"legend_items":legend_items,
                                              "points":total_points,"ui_status":status})
                    print(f"FS1098_MATRIX metric={metric} window={window} STATUS=200 SERIES={len(series)} RENDERED={rendered_series} POINTS={total_points} SVG_PATHS={svg_paths}",flush=True)

            # Rapid window switching: require a fresh 24h API response, not
            # merely the 24h DOM left over from the preceding matrix cell.
            page.locator("#history-window").select_option("1h")
            page.locator("#history-window").select_option("6h")
            with page.expect_response(
                lambda r: "/api/fs1089/prometheus/history" in r.url
                and "metric=scrape_duration" in r.url and "window=24h" in r.url,
                timeout=25000,
            ) as race_response:
                page.locator("#history-window").select_option("24h")
            assert race_response.value.status==200
            race_payload=race_response.value.json()
            assert race_payload.get("metric")=="scrape_duration"
            assert race_payload.get("window")=="24h"
            assert len(race_payload.get("series", []))==5
            page.wait_for_function("""() => {
              const s=document.querySelector('#history-status')?.textContent || '';
              return s.endsWith(' · 24h') && s.includes('points') &&
                !document.querySelector('#history-refresh').disabled;
            }""",timeout=30000)
            assert page.locator("#history-legend > span").count()==5, "stale legend duplication"
            assert page.locator("#history-chart path").count()==5, "stale SVG duplication"
            print("FS1113_RAPID_WINDOW_RACE=PASS",flush=True)

            # Exercise the same cancellation contract for availability as well.
            # An old scrape_duration response must not overwrite the new metric.
            page.locator("#history-metric").select_option("scrape_duration")
            page.locator("#history-window").select_option("1h")
            page.locator("#history-window").select_option("6h")
            with page.expect_response(
                lambda r: "/api/fs1089/prometheus/history" in r.url
                and "metric=availability" in r.url and "window=24h" in r.url,
                timeout=25000,
            ) as metric_race_response:
                page.locator("#history-window").select_option("24h")
                page.locator("#history-metric").select_option("availability")
            assert metric_race_response.value.status==200
            metric_race_payload=metric_race_response.value.json()
            assert metric_race_payload.get("metric")=="availability"
            assert metric_race_payload.get("window")=="24h"
            assert len(metric_race_payload.get("series", []))==5
            page.wait_for_function("""() => {
              const s=document.querySelector('#history-status')?.textContent || '';
              return s.endsWith(' · 24h') && s.includes('points') &&
                !document.querySelector('#history-refresh').disabled;
            }""",timeout=30000)
            assert page.locator("#history-metric").input_value()=="availability"
            assert page.locator("#history-legend > span").count()==5, "metric race legend duplication"
            assert page.locator("#history-chart path").count()==5, "metric race SVG duplication"
            print("FS1113_RAPID_METRIC_RACE=PASS",flush=True)

            # Restore scrape_duration for the existing refresh/mobile assertions.
            with page.expect_response(
                lambda r: "/api/fs1089/prometheus/history" in r.url
                and "metric=scrape_duration" in r.url and "window=24h" in r.url,
                timeout=25000,
            ) as restore_response:
                page.locator("#history-metric").select_option("scrape_duration")
            assert restore_response.value.status==200
            page.wait_for_function("""() => {
              const s=document.querySelector('#history-status')?.textContent || '';
              return s.endsWith(' · 24h') && s.includes('points') &&
                !document.querySelector('#history-refresh').disabled;
            }""",timeout=30000)
            assert page.locator("#history-legend > span").count()==5
            assert page.locator("#history-chart path").count()==5

            # Wait for the refresh response and the corresponding completed render.
            # Checking button.enabled alone can pass before a new request starts.
            with page.expect_response(
                lambda r: "/api/fs1089/prometheus/history" in r.url
                and "metric=scrape_duration" in r.url and "window=24h" in r.url,
                timeout=25000,
            ) as refresh_response:
                page.locator("#history-refresh").click()
            assert refresh_response.value.status==200
            refresh_payload=refresh_response.value.json()
            assert refresh_payload.get("metric")=="scrape_duration", refresh_payload
            assert refresh_payload.get("window")=="24h", refresh_payload
            refresh_series=refresh_payload.get("series")
            assert isinstance(refresh_series,list) and len(refresh_series)==5, refresh_series
            page.wait_for_function("""() => {
              const button=document.querySelector('#history-refresh');
              const status=document.querySelector('#history-status')?.textContent || '';
              return button && !button.disabled && status.includes('points')
                && status.endsWith(' · 24h');
            }""",timeout=30000)
            assert page.locator("#history-chart path").count()==5
            assert page.locator("#history-legend > span").count()==5
            print("FS1098_REFRESH=PASS",flush=True)

            page.set_viewport_size({"width":390,"height":844})
            page.wait_for_timeout(500)
            box=page.locator("#history-chart").bounding_box()
            assert box and box["width"]<=390 and box["width"]>250,("mobile chart width",box)
            assert page.locator("#history-chart path").count()==5, "mobile SVG series mismatch"
            assert page.locator("#history-legend > span").count()==5, "mobile legend duplication"
            assert page.locator("#history-status").inner_text().endswith(" · 24h"), "mobile stale window"
            page.screenshot(path=str(out/"history-mobile.png"),full_page=True)
            report["screenshots"].append("history-mobile.png")
            print("FS1098_MOBILE=PASS WIDTH="+str(round(box["width"],1)),flush=True)

            allowed_favicon=[e for e in http_errors if e["url"]==BASE+"/favicon.ico" and e["status"]==404]
            other_http=[e for e in http_errors if e not in allowed_favicon]
            favicon_console=[e for e in console_errors if e["location"].get("url")==BASE+"/favicon.ico" and "404" in e["text"]]
            other_console=[e for e in console_errors if e not in favicon_console]
            assert not other_http,other_http
            assert not other_console,other_console
            assert not page_errors,page_errors
            unexpected_failed=[e for e in failed_requests if not ("/api/fs1089/prometheus/history" in e["url"] and "ERR_ABORTED" in str(e["failure"]))]
            assert not unexpected_failed,unexpected_failed
            report["events"]={"console_errors":console_errors,"page_errors":page_errors,
                              "failed_requests":failed_requests,"http_errors":http_errors,
                              "history_responses":history_responses}
            print("FS1098_BROWSER_ERRORS=NONE_EXCEPT_CONFIRMED_FAVICON_404",flush=True)
            report["status"]="PASS"
        finally:
            browser.close()
except Exception as e:
    report["errors"].append(type(e).__name__+": "+str(e)[:500])
    print("FS1098_ERROR="+report["errors"][-1],flush=True)
finally:
    target=out/"fs1098-report.json"
    target.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    os.chmod(target,0o600)
    print("FS1098_REPORT="+str(target),flush=True)
    print("FS1098_RESULT="+report["status"],flush=True)
if report["status"]!="PASS":
    sys.exit(1)
