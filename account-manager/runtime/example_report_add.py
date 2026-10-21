# EXAMPLE: in-place updater for a LIVE weekly reporting deck.
# ADDITIVE ONLY — opens the existing deck via Deck.__new__ and appends slides; it must
# NEVER call D.Deck("...") (that constructs a brand-new deck and spawns orphan duplicates).
# Hard rule: never destructively rebuild a live artifact. See the `weekly-report` skill.
#
# Set DECK_PID (the live presentationId) and LOGO_URL (your agency's logo PNG URL) in the
# environment before running. The campaign data below is SYNTHETIC (round placeholder
# numbers) — replace it with the real week's numbers for your account.
import os, sys
# dark_deck + patterns are vendored in deck-engine/ at the package root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "deck-engine")))
import dark_deck as D, patterns as P
PID = os.environ.get("DECK_PID", "")
LOGO = os.environ.get("LOGO_URL", "")
if not PID:
    sys.exit("Set DECK_PID to the live reporting deck's presentationId before running.")
MX,CW=P.MX,P.CW
dk=D.dk
d=D.Deck.__new__(D.Deck); d.pid=PID; d._seq=0; d._used_first=True

def ids(): return [s["objectId"] for s in dk.api("GET",f"/v1/presentations/{PID}?fields=slides.objectId")["body"]["slides"]]
print("before:",len(ids()),"slides")

# --- campaign breakdown table (will become slide 4, footer pg4) ---
# Synthetic numbers (round, internally consistent): spend sums to $2,000, revenue to $5,000 (50 purchases x $100 AOV).
def campaign(sid,reqs):
    P.clean_table(d,reqs,sid,"CAMPAIGN BREAKDOWN","Where the spend went · real-purchase lens",
       ["Campaign","Status","Spend","Purchases","ROAS"],
       [["Brand","Enabled","$200","10","5.00"],
        ["PMax - Core","Enabled","$1,000","30","3.00"],
        ["PMax - Category A","Enabled","$500","10","2.00"],
        ["Demand Gen","Enabled","$300","0","0.00"]],
       sub="Last full week (Mon to Sun) · real purchases (your primary purchase conversion action)",
       source="Source: Google Ads, campaign x conversion action. Revenue $5,000 total · 2.50x blended. Prior wk: 40 purchases · $4,000 · 2.00x.",
       right_cols=(2,3,4))
s1,reqs=d.slide(); campaign(s1,reqs); P.footer(d,reqs,s1,LOGO,page=4); d.flush(reqs)

# --- budget pacing (will become slide 5, footer pg5) ---
# Synthetic: $300/day x 30 days = $9,000 implied budget; 20 days in, pace = $6,000, MTD $5,400 = 90%.
def pacing(sid,reqs):
    P.stat_row(d,reqs,sid,"BUDGET PACING","Underpacing · Demand Gen is under-delivering",
        [("$5,400","MTD spend"),("90%","of budget pace"),("$8,100","projected EOM")])
    d.text(reqs,sid,MX,3520000,CW,340000,
       "Implied monthly budget $9,000 · daily budgets $300/day (Brand $30 · PMax - Core $150 · PMax - Category A $70 · Demand Gen $50).",
       size=10,color=D.TEXT)
    d.text(reqs,sid,MX,3880000,CW,340000,
       "Underpacing because Demand Gen is limited by disapproved ads and under-delivers its $50/day.",
       size=10,color=D.MUTED)
    d.text(reqs,sid,MX,4600000,CW,300000,"Source: Google Ads spend + campaign daily budgets, month to date (day 20 of 30).",size=8.5,color=D.MUTED,italic=True)
s2,reqs=d.slide(); pacing(s2,reqs); P.footer(d,reqs,s2,LOGO,page=5); d.flush(reqs)

# --- move both new slides to index 3 (after the scorecard) ---
dk.api("POST",f"/v1/presentations/{PID}:batchUpdate",{"requests":[
   {"updateSlidesPosition":{"slideObjectIds":[s1,s2],"insertionIndex":3}}]})

# --- fix page numbers on the 3 shifted slides (now positions 5,6,7 -> pages 6,7,8) ---
order=ids(); shifted=order[5:8]; newnums=dict(zip(shifted,["6","7","8"]))
reqs=[]
for sid,newn in newnums.items():
    pg=dk.api("GET",f"/v1/presentations/{PID}/pages/{sid}?fields=pageElements(objectId,transform,shape(text(textElements(textRun(content)))))")["body"]
    for el in pg.get("pageElements",[]):
        tr=el.get("transform",{}); ty=tr.get("translateY",0); tx=tr.get("translateX",0)
        if 4700000<ty<5050000 and tx>8000000:
            cur="".join(t.get("textRun",{}).get("content","") for t in el.get("shape",{}).get("text",{}).get("textElements",[]))
            reqs.append({"insertText":{"objectId":el["objectId"],"text":newn,"insertionIndex":0}})
            reqs.append({"deleteText":{"objectId":el["objectId"],"textRange":{"type":"FIXED_RANGE","startIndex":len(newn),"endIndex":len(newn)+len(cur)}}})
            break
if reqs: dk.api("POST",f"/v1/presentations/{PID}:batchUpdate",{"requests":reqs})
print("after:",len(ids()),"slides · page numbers fixed on shifted slides")
