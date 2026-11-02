import pandas as pd
import pytest
from staticsites.timeseries import baseline_level, rebase, load_series


@pytest.mark.parametrize('frequency,expected',[('M',90),('Q',100)])
def test_calendar_policy_is_explicit(frequency,expected):
    series=pd.Series([90.,100.,110.],index=pd.to_datetime(['2024-04-30','2024-06-30','2024-09-30']))
    assert baseline_level(series,pd.Timestamp('2024-05-15'),frequency=frequency)==expected
    assert rebase(series,pd.Timestamp('2024-05-15'),frequency=frequency).iloc[0]==pytest.approx(9000/expected)


def test_missing_values_do_not_create_a_baseline_or_a_zero_division():
    series=pd.Series([None,0.,10.],index=pd.to_datetime(['2024-01-31','2024-02-29','2024-03-31']))
    with pytest.raises(ValueError,match='No observations'):
        baseline_level(series,'2024-01-01',frequency='M')
    with pytest.raises(ValueError,match='zero'):
        rebase(series,'2024-02-01',frequency='M')
    with pytest.raises(ValueError,match='empty'):
        baseline_level(series.iloc[:1],'2024-01-01',frequency='M')


def test_csv_reader_preserves_nulls_and_sorts_only(tmp_path):
    path=tmp_path/'series.csv'
    path.write_text('date,value\n2024-02-29,0\n2024-01-31,\n')
    frame=load_series(path)
    assert frame.index.is_monotonic_increasing
    assert pd.isna(frame.iloc[0,0]) and frame.iloc[1,0]==0
