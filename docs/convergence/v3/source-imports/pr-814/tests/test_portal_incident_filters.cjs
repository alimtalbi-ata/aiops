const test = require("node:test");
const assert = require("node:assert/strict");
const { matchesIncident } = require("../app/portal/portal_usability.js");
test("case insensitive search",()=>assert.equal(matchesIncident("SAN — SIMULATED","P1"," san ",""),true));
test("priority and search conjunctive",()=>assert.equal(matchesIncident("SAN","P1","san","P2"),false));
test("empty filter restores catalogue",()=>assert.equal(matchesIncident("Payments","P2","",""),true));
test("unknown query never matches",()=>assert.equal(matchesIncident("Payments","P2","missing",""),false));
