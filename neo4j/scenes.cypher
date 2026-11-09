// Four saved queries for the oral defense (8-minute talk). Paste each into Neo4j Browser ahead of
// time and save as a Favorite (star icon), so nothing is typed live. Run in this order.
// Neo4j Browser: http://localhost:7474  (no login needed, auth is off on this local demo instance)

// ============================================================================================
// SCENE 1 (~45s, MUST-HAVE) -- the hook: one tribe
// Say: "No sector classification puts these stocks together -- media, gaming, industrials,
// biotech. But the same funds bet on all of them, because they're all takeover targets.
// Our graph found that without knowing anything about mergers."
// ============================================================================================
MATCH (t:Tribe {quarter: '2026Q2', name: 'Merger arbitrage'})<-[it:IN_TRIBE]-(s:Stock)
OPTIONAL MATCH (m:Manager)-[b:BETS_ON]->(s)
RETURN t, it, s, b, m;

// ============================================================================================
// SCENE 2 (~30s, nice-to-have) -- how a link is born
// Click Electronic Arts, or run this directly. Say: "Two stocks get a link when the same
// managers bet on both, more than chance would predict given their popularity. That's our graph."
// Point at one edge's z (strength of the signal) and shared (how many common bettors).
// ============================================================================================
MATCH (s:Stock {ticker: 'EA*', quarter: '2026Q2'})-[r:CO_BET]-(o:Stock)
RETURN s, r, o
ORDER BY r.z DESC;

// ============================================================================================
// SCENE 3 (~30s, MUST-HAVE) -- zoom out: the tribes map
// All named 2026Q2 tribes, 10 key stocks each (~100 nodes), coloured by tribe (style this once
// in Browser: click a Stock node -> "..." -> colour by sector/tribeId property, or set
// caption = ticker). Say: "Here are all the tribes: Canadian banks, income REITs, blue chips,
// AI hardware and biotech, midstream and private markets... Stocks like Cheniere Energy sit
// between several tribes -- bet on by more than one crowd. If one tribe sells, they're the
// contagion points."  (Cheniere Energy / ticker LNG, participation ~0.62, is loaded and tagged.)
// ============================================================================================
MATCH (t:Tribe {quarter: '2026Q2'})<-[:IN_TRIBE]-(s:Stock)
WHERE s.sceneRank IS NOT NULL
OPTIONAL MATCH (s)-[r:CO_BET]-(o:Stock)
WHERE o.sceneRank IS NOT NULL AND o.quarter = '2026Q2'
RETURN t, s, r, o;

// ============================================================================================
// SCENE 4 (~20s, if time allows) -- same tribe, 2022 vs 2026
// Say: "Merger arbitrage in 2022: Activision, Twitter, Citrix, Zendesk -- 2022's deal targets.
// In 2026: Warner Bros Discovery, EA, Chart Industries -- 2026's deal targets. Different stocks,
// largely the same funds: Gabelli and Verition show up in both years' top bettors."
// ============================================================================================
MATCH (t:Tribe {name: 'Merger arbitrage'})<-[it:IN_TRIBE]-(s:Stock)
OPTIONAL MATCH (m:Manager)-[b:BETS_ON]->(s)
RETURN t, it, s, b, m;

// ---------------------------------------------------------------------------------------------
// Handy checks while rehearsing:
// MATCH (n) RETURN labels(n)[0] AS label, count(*) ORDER BY count(*) DESC;   -- node counts
// MATCH ()-[r]->() RETURN type(r) AS rel, count(*) ORDER BY count(*) DESC;   -- relationship counts
// MATCH (t:Tribe) RETURN t.quarter, t.name, t.sizeFull ORDER BY t.quarter, t.sizeFull DESC;
