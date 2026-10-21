"""The finders load lean rows: same matches as before, and no extra query per row. Fake data."""

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.services.investing.dividend_matching import _new_dividends
from app.services.investing.sweeps import SWEEP_WORDS


def test_sweep_words_agree_with_the_sql_prefilter():
    assert SWEEP_WORDS.search("FAKE DEPOSIT SWEEP")
    assert SWEEP_WORDS.search("fake sweep intra-day")
    assert not SWEEP_WORDS.search("ſweep")  # long s: SQL ILIKE doesn't fold it either


def test_new_dividends_load_in_one_query(client, make_account, add_txn):
    ira = make_account(name="Fake IRA", kind="retirement")["id"]
    for day in range(1, 6):
        add_txn(ira, 100 * day, date=f"2026-09-0{day}", description="FAKE CO DIVIDEND")
    # Added by hand they are found at once; forget that to look at the query alone.
    count = []
    engine = client.app.state.engine
    event.listen(engine, "before_cursor_execute", lambda *a: count.append(1))
    with Session(engine) as session:
        from sqlalchemy import delete

        from app.models import Dividend

        session.execute(delete(Dividend))
        session.commit()
        count.clear()
        found = _new_dividends(session, None)
        assert len(found) == 5
        assert all(t.category_source is None for t in found)
        assert len(count) == 1
