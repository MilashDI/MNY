# MNY project

MNY (Mafia New Year) is a local-only host console for a ten-player, in-person sports mafia game. Keep the source in MilashDI/MNY; do not publish the website unless requested.

Roles: six civilians, one sheriff, two mafia, one don. The host assigns roles manually during the initial night. Each new day starts after the previous actual opener, skipping eliminated players. A muted opener retains nomination rights and still counts as the opener.

Fouls accumulate for the whole game. The host chooses current or next day for the third foul; clicking the three-dot control cycles 0→1→2→3→0; elimination is a separate explicit host action. The timer counts upward indefinitely; no automatic speech cutoff. A single nominee is not voted on the first day; on later days a single nominee gets all votes. Otherwise plurality wins. Finish as soon as remaining unallocated votes cannot change the outcome. Tied leaders alone give extra speeches and enter a revote. Repeated ties allow manual resolution only within the limits in RULES.md. Scoring rules are described below.

Night actions are marks for victim, sheriff check, and don check; never reveal check results. Red wins when all black roles are eliminated; black wins at parity. Persist games locally and retain evening statistics.

No build or third-party dependencies. Run with python3 server.py. Persist all user data in data/mny.sqlite3 through the local API. Keep data/ and user photos out of Git. Browser storage is used only for one-time migration. Run tests with node --test tests/*.test.cjs. Maintain accessible controls and responsive layouts; use restrained winter styling.

Best move (ЛХ) belongs only to the victim killed on the first game night after the first day; a miss that night means no best move later. It is unavailable if two or more players leave by voting or disciplinary removal before the end of the second game night. Night kills do not count toward that limit; later departures do not revoke it. The host records three distinct seat numbers, including the victim’s own number if named, inline beside their nickname.

Repeated three-way tie: with nine alive players and fewer than two completed game nights after the initial role night, lifting all three is prohibited. Keep the extra 30-second speeches and tied-candidate revote; after another tie, leave everyone in. Two completed game nights allow lifting three, including when the second night was a miss. Count Sheriff check opportunities by completed game nights, not recorded check selections.

See RULES.md for the agreed voting, tied-candidate lifting and disciplinary voting-skip rules. Договорка is role assignment only and does not count as a game night. Extra speeches and revotes retain original nomination order. Disqualification penalties are persistent, undoable, corrected when a removed player is restored, and reset by restarting the party.

Scoring is now implemented: every winning team member gets 2 points automatically regardless of elimination or disqualification; losing team gets 0. Extra points are a single signed score from -4 to +2, in 0.2 steps above zero and 0.1 steps below zero. Store integer tenths and validate manual input. Total equals victory points plus extra points. The separate «Протокол игры» opens from the victory card or archived game entries. Roles are aligned in one icon column. Each player's extra score has an optional editable comment saved with the protocol. Archived protocols remain editable without changing another active party. Scores persist locally and count toward evening statistics; restarting a game resets scores and comments.
