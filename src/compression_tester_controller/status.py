import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import logging

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

from typing import List

from compression_testing_data.meta import get_session
from compression_testing_data.models.samples import Sample 
from compression_testing_data.models.testing import CompressionStep, CompressionTrial, ProcessedSTL, FullPointCloud, ProcessedPointCloud, RawSTL 

CONN_STR = 'postgresql://domanlab:dn757657@192.168.1.3:5432/compression_testing'


def get_trials_df(
        session,
        trial_ids,
):
    q = session.query(CompressionTrial).filter(CompressionTrial.id.in_(trial_ids))
    df = pd.read_sql(sql=q.statement, con=session.bind)

    return df


def get_steps_df(
        session,
        trial_ids,
)-> pd.DataFrame :
    trials = session.query(CompressionTrial).\
        filter(CompressionTrial.id.in_(trial_ids))

    all_step_ids = list()
    for trial in trials:
        steps = trial.steps
        step_ids = [step.id for step in steps]
        all_step_ids += step_ids
    
    q = session.query(CompressionStep).filter(CompressionStep.id.in_(all_step_ids))
    df = pd.read_sql(sql=q.statement, con=session.bind)

    return df


def check_full_pcds(
        session,
        step_ids,
):
    
    query = session.query(FullPointCloud).filter(FullPointCloud.compression_step_id.in_(step_ids))
    df = pd.read_sql(sql=query.statement, con=session.bind)
    return df


def check_proc_pcds(
        session,
        step_ids,
):
    
    query = session.query(ProcessedPointCloud).filter(ProcessedPointCloud.compression_step_id.in_(step_ids))
    df = pd.read_sql(sql=query.statement, con=session.bind)
    return df


def check_raw_stls(
        session,
        step_ids,
):
    
    query = session.query(RawSTL).filter(RawSTL.compression_step_id.in_(step_ids))
    df = pd.read_sql(sql=query.statement, con=session.bind)
    return df


def check_proc_stls(
        session,
        step_ids,
):
    
    query = session.query(ProcessedSTL).filter(ProcessedSTL.compression_step_id.in_(step_ids))
    df = pd.read_sql(sql=query.statement, con=session.bind)
    return df


def check_trial_status(
        session,
        trial_ids: List[int],
):
    trials_df = get_trials_df(session=session, trial_ids=trial_ids)
    trials_df = trials_df.rename(columns={'id': 'trial_id'})
    trials_df['st_req'] = (trials_df['strain_limit'] / trials_df['strain_delta_target']) + 1

    sample_ids = trials_df['sample_id'].unique()
    sample_ids = [int(x) for x in sample_ids]

    q = session.query(Sample).filter(Sample.id.in_(sample_ids))
    samples_df = pd.read_sql(sql=q.statement, con=session.bind)

    check_df = trials_df.merge(right=samples_df[['n_perimeters', 'infill_density', 'id']], how='inner', left_on='sample_id', right_on='id')
    check_keep_cols = ['trial_id', 'st_req', 'n_perimeters', 'infill_density']
    check_df = check_df[check_keep_cols]

    steps_df = get_steps_df(session=session, trial_ids=trial_ids)
    
    # group by trial for finishing check_df
    step_ids = steps_df['id'].unique()
    step_ids = [int(x) for x in step_ids]

    steps_df = steps_df.set_index(keys=['id'], drop=True)
    steps_df.sort_index(inplace=True)

    full_pcds_df = check_full_pcds(session=session, step_ids=step_ids)
    proc_pcds_df = check_proc_pcds(session=session, step_ids=step_ids)
    raw_stls_df = check_raw_stls(session=session, step_ids=step_ids)
    proc_stls_df = check_proc_stls(session=session, step_ids=step_ids)

    steps_df['full_pcd'] = steps_df.index.isin(full_pcds_df['compression_step_id'])
    steps_df['proc_pcd'] = steps_df.index.isin(proc_pcds_df['compression_step_id'])
    steps_df['raw_stl'] = steps_df.index.isin(raw_stls_df['compression_step_id'])
    steps_df['proc_stl'] = steps_df.index.isin(proc_stls_df['compression_step_id'])

    num_steps = steps_df.groupby('compression_trial_id')['full_pcd'].size()
    check_df['st_rec'] = check_df['trial_id'].map(num_steps)

    full_pcds = steps_df.groupby('compression_trial_id')['full_pcd'].sum()
    check_df['full_pcds'] = check_df['trial_id'].map(full_pcds)

    proc_pcds = steps_df.groupby('compression_trial_id')['proc_pcd'].sum()
    check_df['proc_pcds'] = check_df['trial_id'].map(proc_pcds)

    raw_stls = steps_df.groupby('compression_trial_id')['raw_stl'].sum()
    check_df['raw_stls'] = check_df['trial_id'].map(raw_stls)

    proc_stls = steps_df.groupby('compression_trial_id')['proc_stl'].sum()
    check_df['proc_stls'] = check_df['trial_id'].map(proc_stls)

    check_df = check_df.sort_values(by=['n_perimeters', 'infill_density'], ascending=[True, True])

    # Set pandas display options
    pd.set_option('display.max_rows', None)  # Show all rows
    pd.set_option('display.max_columns', None)  # Show all columns
    pd.set_option('display.width', None)  # Auto-detect the display width
    pd.set_option('display.max_colwidth', None)  # Show full content of each column

    # Print the full DataFrame
    print(check_df)

    pass


def trial_ids_by_testset(test_set_ids, session):

    query = session.query(CompressionTrial).filter(CompressionTrial.test_set_id.in_(test_set_ids))
    df = pd.read_sql(sql=query.statement, con=session.bind)
    
    trial_ids = df['id'].unique()
    trial_ids = [int(x) for x in trial_ids]

    return trial_ids


def all_trial_ids(session):

    query = session.query(CompressionTrial).filter(CompressionTrial.sample_id.is_not(None))
    df = pd.read_sql(sql=query.statement, con=session.bind)
    
    trial_ids = df['id'].unique()
    trial_ids = [int(x) for x in trial_ids]

    return trial_ids


def main():
    Session = get_session(conn_str=CONN_STR)
    session = Session()

    trial_ids = all_trial_ids(session=session)
    trial_ids = trial_ids_by_testset(test_set_ids=['63d75ec4-c367-4e4a-8902-998b58ddb051'], session=session)

    check_trial_status(session=session, trial_ids=trial_ids)

    pass


if __name__ == '__main__':
    main()