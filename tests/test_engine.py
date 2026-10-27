from pathlib import Path
import sqlite3
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from app.generator import generate_dataset, validate_dataset
from app.engine import load_data, compute_portfolio, create_proposal


def make_data(tmp_path):
    generate_dataset(tmp_path, portfolios=6, instruments=30, trading_days=20, seed=20261022)
    return load_data(tmp_path)


def test_generator_is_valid_and_reproducible(tmp_path):
    a=tmp_path/'a'; b=tmp_path/'b'
    generate_dataset(a,6,30,20,20261022); generate_dataset(b,6,30,20,20261022)
    assert validate_dataset(a)['valid'] is True
    assert (a/'holdings.csv').read_bytes() == (b/'holdings.csv').read_bytes()
    assert (a/'market_prices.csv').read_bytes() == (b/'market_prices.csv').read_bytes()


def test_portfolio_allocation_and_foreign_keys(tmp_path):
    data=make_data(tmp_path)
    pid=data['portfolios'].iloc[0].portfolio_id
    result=compute_portfolio(pid,data)
    assert result['target_weights_valid'] is True
    assert result['total_value'] > 0
    assert abs(sum(x['target_weight'] for x in result['allocation'])-1) < 1e-6


def test_proposal_persists_append_only_events(tmp_path):
    data=make_data(tmp_path); db=tmp_path/'events.db'
    pid=data['portfolios'].iloc[0].portfolio_id
    first=create_proposal(pid,data,db); second=create_proposal(pid,data,db)
    import sqlite3
    with sqlite3.connect(db) as con:
        count=con.execute('select count(*) from proposal_events').fetchone()[0]
    assert count == 2
    assert first['proposal_id'] != second['proposal_id']
    assert first['status'] in {'PROPOSED','NO_TRADE','REJECTED'}
    with sqlite3.connect(db) as con:
        con.execute('PRAGMA foreign_keys = ON')
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                "INSERT INTO trade_events "
                "(proposal_id, trade_id, created_at, payload_json) VALUES (?,?,?,?)",
                ('PROPOSAL-MISSING', 'TRADE-INVALID', '2026-01-01T00:00:00Z', '{}')
            )


def test_unknown_portfolio_fails(tmp_path):
    data=make_data(tmp_path)
    try: compute_portfolio('PORT-DOES-NOT-EXIST',data)
    except KeyError: pass
    else: raise AssertionError('Unknown portfolio should raise KeyError')


def test_invalid_target_weights_are_rejected(tmp_path):
    data=make_data(tmp_path); db=tmp_path/'events.db'
    pid=data['portfolios'].iloc[0].portfolio_id
    idx=data['target_allocations'].index[data['target_allocations'].portfolio_id==pid][0]
    data['target_allocations'].loc[idx,'target_weight']=0.99
    proposal=create_proposal(pid,data,db)
    assert proposal['status']=='REJECTED'
    assert proposal['exceptions'][0]['issue_type']=='WEIGHTS_NOT_100'


def test_excluded_instruments_never_buy_proposed(tmp_path):
    data=make_data(tmp_path); pid=data['portfolios'].iloc[0].portfolio_id
    proposal=create_proposal(pid,data,tmp_path/'events.db')
    excluded=set(data['instruments'].loc[data['instruments'].is_excluded,'instrument_id'])
    assert not any(t['side']=='BUY' and t['instrument_id'] in excluded for t in proposal['trades'])


def test_generator_rejects_unsupported_scale(tmp_path):
    for kwargs in (
        {"portfolios": 0},
        {"portfolios": 1001},
        {"portfolios": 1, "instruments": 5001},
        {"portfolios": 1, "instruments": 5, "trading_days": 251},
    ):
        with pytest.raises(ValueError):
            generate_dataset(tmp_path / str(len(kwargs)), **kwargs)


def test_stale_price_is_flagged_and_not_used_for_trade(tmp_path):
    data=make_data(tmp_path)
    pid=data['portfolios'].iloc[0].portfolio_id
    instrument_id=data['holdings'].iloc[0].instrument_id
    data['market_prices'].loc[
        data['market_prices'].instrument_id == instrument_id, 'price_date'
    ] = '2025-01-01'
    proposal=create_proposal(pid,data,tmp_path/'events.db')
    assert any(
        e['issue_type'] == 'STALE_PRICE' and e['instrument_id'] == instrument_id
        for e in proposal['exceptions']
    )
    assert not any(t['instrument_id'] == instrument_id for t in proposal['trades'])


def test_trade_fee_is_reconciled_and_excess_sell_is_capped(tmp_path):
    data=make_data(tmp_path)
    pid=data['portfolios'].iloc[0].portfolio_id
    holding=data['holdings'].iloc[0]
    instrument_id=holding.instrument_id
    second_instrument_id=data['holdings'].iloc[1].instrument_id
    data['instruments'].loc[
        data['instruments'].instrument_id == second_instrument_id, 'asset_class'
    ] = 'Equity'
    data['target_allocations'].loc[
        data['target_allocations'].portfolio_id == pid, 'target_weight'
    ] = [0.0, 1.0, 0.0, 0.0, 0.0]
    proposal=create_proposal(pid,data,tmp_path/'events.db')
    assert any(e['issue_type'] == 'TRADE_EXCEEDS_HOLDING_PREVENTED'
               for e in proposal['exceptions'])
    for trade in proposal['trades']:
        if trade['instrument_id'] == instrument_id:
            assert trade['quantity'] <= float(holding.quantity)
            tier=data['instruments'].set_index('instrument_id').loc[
                instrument_id, 'liquidity_tier'
            ]
            schedule=data['fee_schedules'].set_index('tier').loc[tier]
            expected_fee=max(
                float(schedule.minimum_fee),
                trade['trade_value'] * float(schedule.rate_bps) / 10000,
            )
            assert trade['estimated_fee'] == round(expected_fee, 2)


def test_ground_truth_labels_are_separate_from_engine_inputs(tmp_path):
    generate_dataset(tmp_path, 6, 30, 20, 20261022)
    assert 'ground_truth' not in load_data(tmp_path)
    labels=pd.read_csv(tmp_path/'ground_truth.csv')
    assert set(labels.issue_type) == {
        'WEIGHTS_NOT_100', 'TRADE_EXCEEDS_HOLDING', 'EXCLUDED_INSTRUMENT',
        'FEES_OMITTED', 'STALE_PRICE_UNFLAGGED'
    }


def _set_targets_to_current_weights(data, pid, shift):
    snapshot=compute_portfolio(pid, data)
    weights={row['asset_class']: row['current_weight'] for row in snapshot['allocation']}
    target_rows=data['target_allocations'].index[
        data['target_allocations'].portfolio_id == pid
    ].tolist()
    assets=data['target_allocations'].loc[target_rows, 'asset_class'].tolist()
    first, second=assets[:2]
    weights[first] += shift
    weights[second] -= shift
    data['target_allocations'].loc[target_rows, 'target_weight'] = [
        weights[asset] for asset in assets
    ]


@pytest.mark.parametrize('shift, expected_trades', [(0.01, 0), (0.03, 0), (0.04, 1)])
def test_drift_tolerance_below_at_and_above(tmp_path, shift, expected_trades):
    data=make_data(tmp_path)
    pid=data['portfolios'].iloc[0].portfolio_id
    _set_targets_to_current_weights(data, pid, shift)
    data['constraints'].loc[
        (data['constraints'].portfolio_id == pid)
        & (data['constraints'].constraint_type == 'DRIFT_TOLERANCE'), 'value'
    ] = 0.03
    proposal=create_proposal(pid, data, tmp_path / f'{shift}.db')
    assert len(proposal['trades']) >= expected_trades
    if shift <= 0.03:
        assert proposal['status'] == 'NO_TRADE'
    else:
        assert proposal['status'] == 'PROPOSED'


def test_excluded_instrument_is_never_recommended_for_sell(tmp_path):
    data=make_data(tmp_path)
    pid=data['portfolios'].iloc[0].portfolio_id
    instrument_id=data['holdings'].iloc[0].instrument_id
    data['instruments'].loc[
        data['instruments'].instrument_id == instrument_id, 'is_excluded'
    ] = True
    data['target_allocations'].loc[
        data['target_allocations'].portfolio_id == pid, 'target_weight'
    ] = [0.0, 1.0, 0.0, 0.0, 0.0]
    proposal=create_proposal(pid, data, tmp_path/'events.db')
    assert not any(t['instrument_id'] == instrument_id for t in proposal['trades'])


def test_missing_fee_schedule_is_explicitly_blocked(tmp_path):
    data=make_data(tmp_path)
    pid=data['portfolios'].iloc[0].portfolio_id
    _set_targets_to_current_weights(data, pid, 0.04)
    data['fee_schedules']=data['fee_schedules'][
        data['fee_schedules'].tier != 'HIGH'
    ]
    proposal=create_proposal(pid, data, tmp_path/'events.db')
    assert any(e['issue_type'] == 'FEES_MISSING' for e in proposal['exceptions'])
    assert all(t['estimated_fee'] >= 0 for t in proposal['trades'])


def test_seed_sql_rejects_duplicate_and_invalid_foreign_keys(tmp_path):
    generate_dataset(tmp_path, 6, 30, 20, 20261022)
    db=tmp_path/'seed.db'
    with sqlite3.connect(db) as con:
        con.execute('PRAGMA foreign_keys = ON')
        con.executescript((tmp_path/'seed.sql').read_text(encoding='utf-8'))
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                "INSERT INTO portfolios VALUES (?,?,?,?,?,?)",
                ('PORT-DUP', 'INV-MISSING', 'bad', 'USD', 'ACTIVE', '2025-01-01')
            )
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                "INSERT INTO instruments VALUES (?,?,?,?,?,?,?,?)",
                ('INS-DUP', 'SYN0001', 'bad', 'Equity', 'USD', 0, 'HIGH', 1)
            )
        assert con.execute('PRAGMA foreign_keys').fetchone()[0] == 1


def test_api_success_and_invalid_requests():
    from app.main import app
    with TestClient(app) as client:
        health=client.get('/api/health')
        assert health.status_code == 200
        portfolios=client.get('/api/portfolios')
        assert portfolios.status_code == 200
        portfolio_id=portfolios.json()[0]['portfolio_id']
        detail=client.get(f'/api/portfolios/{portfolio_id}')
        assert detail.status_code == 200
        proposal=client.post(f'/api/portfolios/{portfolio_id}/rebalance')
        assert proposal.status_code == 200
        assert proposal.json()['estimated_fees'] >= 0
        assert client.get('/api/portfolios/PORT-DOES-NOT-EXIST').status_code == 404
        assert client.post('/api/admin/regenerate?portfolios=0').status_code == 400
