import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import logging
import datetime

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

from compression_testing_data.meta import get_session
from compression_testing_data.models.samples import Sample 
from compression_testing_data.models.testing import CompressionStep, CompressionTrial, ProcessedSTL 

CONN_STR = 'postgresql://domanlab:dn757657@192.168.1.2:5432/compression_testing'


def get_samples_df(
        session,
        perims = None, 
        infills = None,
        duplicates: bool = False
        ):
    
    if perims and infills:
        query = session.query(Sample).\
            filter(Sample.n_perimeters.in_(perims)).\
            filter(Sample.infill_density.in_(infills))
    elif perims:
        query = session.query(Sample).\
            filter(Sample.n_perimeters.in_(perims))
    elif infills:
        query = session.query(Sample).\
            filter(Sample.infill_density.in_(infills))
    else:
        query = session.query(Sample)

    df = pd.read_sql(sql=query.statement, con=session.bind)
    
    if not duplicates:
        df = df.sort_values(by='created_at', ascending=False)
        df = df.drop_duplicates(subset=['infill_pattern', 'infill_density', 'n_perimeters'], keep='first')

    return df


def get_trials_df(
        session,
        perims, 
        infills, 
):
    samples_df = get_samples_df(infills=infills, perims=perims, session=session)
    sample_ids = samples_df['id'].unique()
    sample_ids = [int(x) for x in sample_ids]

    query = session.query(CompressionTrial).\
        filter(CompressionTrial.sample_id.in_(sample_ids))

    df = pd.read_sql(sql=query.statement, con=session.bind)
    return df


def get_steps_df(
        session,
        perims = None, 
        infills = None, 
):
    trials_df = get_trials_df(infills=infills, perims=perims, session=session)  
    trial_ids = trials_df['id'].unique()
    trial_ids = [int(x) for x in trial_ids]

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


def get_volume_df(
        session,
        perims = None, 
        infills = None, 
):
    
    steps_df = get_steps_df(infills=infills, perims=perims, session=session)
    step_ids = steps_df['id'].unique()
    step_ids = [int(x) for x in step_ids]

    query = session.query(ProcessedSTL).filter(ProcessedSTL.compression_step_id.in_(step_ids))

    df = pd.read_sql(sql=query.statement, con=session.bind)

    return df


def get_sample_label(sample, vol_init: float = None):

    label = f"{sample.infill_pattern} Infill Pattern\n{round(sample.infill_density * 100, 0)}% Infill Density\n{sample.n_perimeters} Perimeters\nheight = {round(sample.height_enc, 2)}"

    avg_diam = None 
    if vol_init:
        pir2 = vol_init / sample.height_enc
        r2 = pir2 / np.pi
        r = np.sqrt(r2)
        avg_diam = r * 2

        label = label + f"\n d_avg = {round(avg_diam, 2)}"
    
    return label


def volume_vs_strain(
        session,
        title: str = 'Volume vs. Engineering Strain',
        infills = None,
        perims = None
):  
    trials_df = get_trials_df(infills=infills, perims=perims, session=session)
    trials_df.drop(columns=['created_at'], inplace=True)
    
    steps_df = get_steps_df(infills=infills, perims=perims, session=session)
    steps_df.drop(columns=['created_at'], inplace=True)
    
    volume_df = get_volume_df(infills=infills, perims=perims, session=session)
    volume_df.drop(columns=['id', 'created_at'], inplace=True)

    sample_df = get_samples_df(infills=infills, perims=perims, session=session)
    sample_df.drop(columns=['created_at'], inplace=True)

    df = steps_df.merge(volume_df, how='inner', left_on='id', right_on='compression_step_id')
    df.rename(columns={'id': 'step_id'})

    df = df.merge(trials_df, how='inner', left_on='compression_trial_id', right_on='id')
    df = df.merge(sample_df, how='inner', left_on='sample_id', right_on='id')

    df.sort_values(by='infill_density', inplace=True)

    fig, ax = plt.subplots()
    sample_ids = df['sample_id'].unique()

    for id in sample_ids:
        sdf = df.loc[df['sample_id'] == id]
        sdf.sort_values(by='strain_encoder', inplace=True)

        sample = session.query(Sample).filter(Sample.id == int(id)).first()
        vol_init = sdf.loc[(df['sample_id'] == id) &  (df['strain_encoder'] == 0)]['volume'].values[0]
        label = get_sample_label(sample=sample, vol_init=vol_init)

        ax.plot(sdf['strain_encoder'], sdf['volume'], label=label)
    
    vol_unit = df['volume_unit'].unique()[0]

    ax.grid()
    ax.set(xlabel='Strain', ylabel=f'Volume [{vol_unit}]',
        title=title)
    ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))
    
    fname = get_filename(title=title, infills=infills, perims=perims)
    fig.savefig(fname=fname, bbox_inches='tight', pad_inches=0.1)

    return


def get_filename(title, infills , perims):
    t = title.translate({ord(i): None for i in '. '})
    str_date = datetime.datetime.now().__str__().translate({ord(i): None for i in ':-. '})
    fname=f"{t}&infills{'_'.join([str(x * 100) for x in infills])}&perims{'_'.join([str(x) for x in perims])}_{str_date}.jpg"
    fname = "./plots/" + fname
    return fname


def auxetic_vs_strain(
        session,
        title: str = 'Auxeticness vs. Engineering Strain',
        infills = None,
        perims = None
):  
    trials_df = get_trials_df(infills=infills, perims=perims, session=session)
    trials_df.drop(columns=['created_at'], inplace=True)
    
    steps_df = get_steps_df(infills=infills, perims=perims, session=session)
    steps_df.drop(columns=['created_at'], inplace=True)
    
    volume_df = get_volume_df(infills=infills, perims=perims, session=session)
    volume_df.drop(columns=['id', 'created_at'], inplace=True)

    sample_df = get_samples_df(infills=infills, perims=perims, session=session)
    sample_df.drop(columns=['created_at'], inplace=True)

    df = steps_df.merge(volume_df, how='inner', left_on='id', right_on='compression_step_id')
    df.rename(columns={'id': 'step_id'})

    df = df.merge(trials_df, how='inner', left_on='compression_trial_id', right_on='id')
    df = df.merge(sample_df, how='inner', left_on='sample_id', right_on='id')

    df.sort_values(by='infill_density', inplace=True)

    fig, ax = plt.subplots()
    sample_ids = df['sample_id'].unique()

    for id in sample_ids:
        sdf = df.loc[df['sample_id'] == id]
        sdf.sort_values(by='strain_encoder', inplace=True)

        sample = session.query(Sample).filter(Sample.id == int(id)).first()
        vol_init = sdf.loc[(df['sample_id'] == id) &  (df['strain_encoder'] == 0)]['volume'].values[0]
        label = get_sample_label(sample=sample, vol_init=vol_init)

        ax.plot(sdf['strain_encoder'], sdf['volume'] / vol_init, label=label)
    
    vol_unit = df['volume_unit'].unique()[0]

    ax.grid()
    ax.set(xlabel='Strain', ylabel=f'Volume [{vol_unit}]',
        title=title)
    ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))

    fname = get_filename(title=title, infills=infills, perims=perims)
    fig.savefig(fname=fname, bbox_inches='tight', pad_inches=0.1)

    return



    # fig, ax = plt.subplots()
    #                 if step.strain_encoder == 0:
    #                     vol_init = stls[0].volume

    #     # fig, ax = plt.subplots()
    #     if len(volume) > 0:
    #         ind = np.argsort(strain)

    #         strain = strain[ind]
    #         volume = volume[ind] / vol_init

    #         ax.plot(strain, volume)
            
    #         label = f"{sample.infill_pattern} Infill Pattern\n{sample.infill_density * 100}% Infill Density\n{sample.n_perimeters} Perimeters\nh = {sample.height_enc}"

    #         avg_diam = None 
    #         if vol_init:
    #             pir2 = vol_init / sample.height_enc
    #             r2 = pir2 / np.pi
    #             r = np.sqrt(r2)
    #             avg_diam = r * 2

    #             label = label + f"\n d_avg = {avg_diam}"
            
    #         ax.plot(strain, volume, label=label)

    # ax.set(xlabel='Strain', ylabel=f'Volume {vol_unit}',
    #     title='graph')
    # ax.grid()
    # # ax.legend()
    # ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))

    # fig.savefig("test.png", bbox_inches='tight')
    # # plt.show()

    return plt


def force_vs_strain(
        session,
        title: str = 'Force vs. Engineering Strain',
        infills = None,
        perims = None
):  
    trials_df = get_trials_df(infills=infills, perims=perims, session=session)
    trials_df.drop(columns=['created_at'], inplace=True)
    
    steps_df = get_steps_df(infills=infills, perims=perims, session=session)
    steps_df.drop(columns=['created_at'], inplace=True)
    
    volume_df = get_volume_df(infills=infills, perims=perims, session=session)
    volume_df.drop(columns=['id', 'created_at'], inplace=True)

    sample_df = get_samples_df(infills=infills, perims=perims, session=session)
    sample_df.drop(columns=['created_at'], inplace=True)

    df = steps_df.merge(volume_df, how='inner', left_on='id', right_on='compression_step_id')
    df.rename(columns={'id': 'step_id'})

    df = df.merge(trials_df, how='inner', left_on='compression_trial_id', right_on='id')
    df = df.merge(sample_df, how='inner', left_on='sample_id', right_on='id')

    df.sort_values(by='infill_density', inplace=True)

    fig, ax = plt.subplots()
    sample_ids = df['sample_id'].unique()

    for id in sample_ids:
        sdf = df.loc[df['sample_id'] == id]
        sdf.sort_values(by='strain_encoder', inplace=True)

        sample = session.query(Sample).filter(Sample.id == int(id)).first()
        vol_init = sdf.loc[(df['sample_id'] == id) &  (df['strain_encoder'] == 0)]['volume'].values[0]
        label = get_sample_label(sample=sample, vol_init=vol_init)

        ax.plot(sdf['strain_encoder'], sdf['force'], label=label)
    
    vol_unit = volume_df['volume_unit'].unique()[0]

    ax.grid()
    ax.set(xlabel='Strain', ylabel=f'Volume [{vol_unit}]',
        title=title)
    ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))

    fname = get_filename(title=title, infills=infills, perims=perims)
    fig.savefig(fname=fname, bbox_inches='tight', pad_inches=0.1)

    return


def main():
    Session = get_session(conn_str=CONN_STR)
    session = Session()

    perim_groups = list()

    infills = [x / 10 for x in range(1, 10, 1)]
    
    perim_groups.append([0])
    perim_groups.append([1])
    perim_groups.append([2])
    perim_groups.append([0, 1, 2])

    # exlude_infills = [0.4]
    # infills = [x for x in infills if x not in exlude_infills]

    # infills = [0.4]

    for perims in perim_groups:
        volume_vs_strain(infills=infills, perims=perims, session=session)
        auxetic_vs_strain(infills=infills, perims=perims, session=session)
        force_vs_strain(infills=infills, perims=perims, session=session)

    return

if __name__ == '__main__':
    main()

