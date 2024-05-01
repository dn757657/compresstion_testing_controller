import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import logging
import datetime
import scienceplots

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

from typing import List, Dict
from scipy.integrate import simpson

from compression_testing_data.meta import get_session
from compression_testing_data.models.samples import Sample 
from compression_testing_data.models.testing import CompressionStep, CompressionTrial, ProcessedSTL 

CONN_STR = 'postgresql://domanlab:dn757657@192.168.1.3:5432/compression_testing'


def get_sample_label(
        id: int,
        conn_str: str = CONN_STR,
        diam: bool = True,
        height: bool = True,
        infill_density: bool = False,
        infill_pattern: bool = True,
        relative_density: bool = True,
        n_perims: bool = True
    ):

    Session = get_session(conn_str=conn_str)
    session = Session()

    query = session.query(CompressionTrial, CompressionStep, Sample, ProcessedSTL).\
        filter(CompressionTrial.id == int(id)).\
        join(Sample, CompressionTrial.sample_id == Sample.id).\
        join(CompressionStep, CompressionTrial.id == CompressionStep.compression_trial_id).\
        join(ProcessedSTL, CompressionStep.id == ProcessedSTL.compression_step_id)
    df = pd.read_sql(sql=query.statement, con=session.bind)

    items = list()

    if infill_pattern:
        infill_pattern = df['infill_pattern'].unique()[0]
        items.append(f"{infill_pattern} Infill Pattern")

    if infill_density:
        infill_density = df['infill_density'].unique()[0]
        items.append(f"{int(round(infill_density * 100, 0))}\\% Infill Density")

    if relative_density:
        relative_density = df['relative_density'].unique()[0]
        items.append(f"{int(round(relative_density * 100, 0))}\\% Relative Density")

    if n_perims:
        n_perims = df['n_perimeters'].unique()[0]
        items.append(f"{n_perims} Perimeters")

    if height:
        sample_height = df['height_enc'].unique()[0]
        items.append(f"Height = {round(sample_height, 2)}")

    if diam:
        vol_init = df.loc[df['strain_encoder'].idxmin(), 'volume']
        avg_diam = None 
        if vol_init:
            pir2 = vol_init / sample_height
            r2 = pir2 / np.pi
            r = np.sqrt(r2)
            avg_diam = r * 2
            items.append(f"Avg. Diam. = {round(avg_diam, 2)}")
    
    label = '\n'.join(items)
    session.close()

    return label


def get_filename(title, data_df):

    infills = data_df['infill_density'].unique()
    perims = data_df['n_perimeters'].unique()

    t = title.translate({ord(i): None for i in '. '})
    str_date = datetime.datetime.now().__str__().translate({ord(i): None for i in ':-. '})
    fname=f"{t}&infills{'_'.join([str(x * 100) for x in infills])}&perims{'_'.join([str(x) for x in perims])}_{str_date}.jpg"
    fname = "\\\\192.168.1.3\\main\\dn_plots\\" + fname
    return fname


def volume_vs_strain(
        data_df: pd.DataFrame,
        title: str = 'Volume vs. Engineering Strain',
):  
    trial_ids = data_df['id'].unique()
    fig, ax = plt.subplots()

    for id in trial_ids:
        tdf = data_df.loc[data_df['id'] == id]

        if not tdf.empty:
            tdf.sort_values(by='strain_encoder', inplace=True)
            vol_init = tdf.loc[tdf['strain_encoder'].idxmin(), 'volume']
            label = get_sample_label(trial_df=tdf)

            ax.plot(tdf['strain_encoder'], tdf['volume'], label=label)
    
    vol_unit = data_df['volume_unit'].unique()[0]

    ax.grid()
    ax.set(xlabel='Strain', ylabel=f'Volume [{vol_unit}]',
        title=title)
    ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))
    
    infills = data_df['infill_density'].unique()
    perims = data_df['n_perimeters'].unique()

    fname = get_filename(title=title, infills=infills, perims=perims)
    fig.savefig(fname=fname, bbox_inches='tight', pad_inches=0.1)

    return


def auxetic_vs_strain(
        data_df: pd.DataFrame,
        title: str = 'Auxeticness vs. Engineering Strain',
):  
    trial_ids = data_df['id'].unique()

    fig, ax = plt.subplots()
    # ax.grid()
    # ax.set(xlabel='Strain', ylabel=f'Volume / V0',
    #     title=title)
    # ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))

    for id in trial_ids:
        tdf = data_df.loc[data_df['id'] == id]

        if not tdf.empty:
            tdf.sort_values(by='strain_encoder', inplace=True)
            vol_init = tdf.loc[tdf['strain_encoder'].idxmin(), 'volume']
            label = get_sample_label(trial_df=tdf)

            ax.plot(tdf['strain_encoder'], tdf['volume'] / vol_init, label=label)
            # plt.show()
    ax.grid()
    ax.set(xlabel='Strain', ylabel=f'Volume / V0',
        title=title)
    ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))
    
    infills = data_df['infill_density'].unique()
    perims = data_df['n_perimeters'].unique()

    fname = get_filename(title=title, infills=infills, perims=perims)
    fig.savefig(fname=fname, bbox_inches='tight', pad_inches=0.1)

    return


def volstrain_vs_strain(
        trial_ids: List[int],
        session,
        xcol: str = 'strain_encoder',
        ycol: str = 'volstrain'
):  

    query = session.query(CompressionTrial, CompressionStep, Sample, ProcessedSTL).\
            filter(CompressionTrial.id.in_(trial_ids)).\
            join(CompressionStep, CompressionTrial.id == CompressionStep.compression_trial_id).\
            join(Sample, CompressionTrial.sample_id == Sample.id).\
            join(ProcessedSTL, CompressionStep.id == ProcessedSTL.compression_step_id)
    df = pd.read_sql(sql=query.statement, con=session.bind)
    df  = df.sort_values(by=['n_perimeters', 'infill_density'], ascending=[True, True])

    dfs = dict()

    trial_ids = df['id'].unique()
    for id in trial_ids:
        tdf = df.loc[df['id'] == id, :].copy()

        if not tdf.empty:
            tdf.sort_values(by=xcol, inplace=True)

            vol_init = tdf.loc[tdf['strain_encoder'].idxmin(), 'volume']
            tdf['deltaV'] = abs(tdf['volume'] - vol_init)
            tdf[ycol] = tdf['deltaV'] / vol_init

            tdf = tdf[[xcol, ycol]]
            tdf = tdf.rename(columns={xcol: 'x', ycol: 'y'})

            dfs[id] = tdf

    return dfs


def force_vs_strain(
        trial_ids: List[int],
        session,
        xcol: str = 'strain_encoder',
        ycol: str = 'force'
):  

    query = session.query(CompressionTrial, CompressionStep, Sample, ProcessedSTL).\
            filter(CompressionTrial.id.in_(trial_ids)).\
            join(CompressionStep, CompressionTrial.id == CompressionStep.compression_trial_id).\
            join(Sample, CompressionTrial.sample_id == Sample.id).\
            join(ProcessedSTL, CompressionStep.id == ProcessedSTL.compression_step_id)
    df = pd.read_sql(sql=query.statement, con=session.bind)
    df  = df.sort_values(by=['n_perimeters', 'infill_density'], ascending=[True, True])

    dfs = dict()

    trial_ids = df['id'].unique()
    for id in trial_ids:
        tdf = df.loc[df['id'] == id, :].copy()

        if not tdf.empty:
            tdf.sort_values(by=xcol, inplace=True)

            tdf = tdf[[xcol, ycol]]
            tdf = tdf.rename(columns={xcol: 'x', ycol: 'y'})

            dfs[id] = tdf

    return dfs


def force_normbyreldensity_vs_strain(
        trial_ids: List[int],
        session,
        xcol: str = 'strain_encoder',
        ycol: str = 'force'
):  

    query = session.query(CompressionTrial, CompressionStep, Sample, ProcessedSTL).\
            filter(CompressionTrial.id.in_(trial_ids)).\
            join(CompressionStep, CompressionTrial.id == CompressionStep.compression_trial_id).\
            join(Sample, CompressionTrial.sample_id == Sample.id).\
            join(ProcessedSTL, CompressionStep.id == ProcessedSTL.compression_step_id)
    df = pd.read_sql(sql=query.statement, con=session.bind)
    df  = df.sort_values(by=['n_perimeters', 'infill_density'], ascending=[True, True])

    dfs = dict()

    trial_ids = df['id'].unique()
    for id in trial_ids:
        tdf = df.loc[df['id'] == id, :].copy()

        if not tdf.empty:
            tdf.sort_values(by=xcol, inplace=True)

            force_init = tdf.loc[tdf['strain_encoder'].idxmin(), 'force']
            relative_density = tdf.loc[tdf['compression_trial_id'] == id, 'relative_density'].unique()[0]
            tdf[ycol] = (tdf[ycol] - force_init) / relative_density

            tdf = tdf[[xcol, ycol]]
            tdf = tdf.rename(columns={xcol: 'x', ycol: 'y'})

            dfs[id] = tdf

    return dfs


def strain_energy_vs_infill(
        data_dfs: List[pd.DataFrame],
        title: str = 'Strain Energy vs Infill'
):
    
    fig, ax = plt.subplots()

    for data_df in data_dfs:

        trial_ids = data_df['id'].unique()
        senergys = list()

        for id in trial_ids:
            tdf = data_df.loc[data_df['id'] == id]

            if not tdf.empty:
                force_zero = tdf.loc[tdf.index.min(), 'force']
                
                tdf.sort_values(by='strain_encoder', inplace=True)

                strains = tdf['strain_encoder']
                forces = tdf['force'] - force_zero

                senergy = simpson(y=forces, x=strains)
                senergys.append([tdf['infill_density'].unique()[0] * 100, senergy])
        
        label = f"{tdf['n_perimeters'].unique()[0]} Perimeters"

        df = pd.DataFrame(senergys, columns=['infill', 'strain_energy'])
        ax.plot(df['infill'], df['strain_energy'], label=label)

    ax.grid()
    ax.set(xlabel='Infill [%]', ylabel=f'Strain Energy',
        title=title)
    ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))

    infills = data_df['infill_density'].unique()
    perims = data_df['n_perimeters'].unique()

    fname = get_filename(title=title, infills=infills, perims=perims)
    fig.savefig(fname=fname, bbox_inches='tight', pad_inches=0.1)
    

def new_plot(        
        nofill_data_df: pd.DataFrame,
        fill_data_df: pd.DataFrame,
        both_data_df: pd.DataFrame,
        title: str = 'Force vs. Engineering Strain',
):  
    fig, ax = plt.subplots()

    nofill_trial_ids = nofill_data_df['id'].unique().tolist()
    fill_trial_ids = fill_data_df['id'].unique().tolist()
    both_trial_ids = both_data_df['id'].unique().tolist()

    trial_ids = nofill_trial_ids + fill_trial_ids + both_trial_ids
    for id in trial_ids:
        if id in nofill_trial_ids:
            data_df = nofill_data_df
        elif id in fill_trial_ids:
            data_df = fill_data_df
        if id in both_trial_ids:
            data_df = both_data_df

        tdf = data_df.loc[data_df['id'] == id]

        if not tdf.empty:
            force_zero = tdf['force'].min()
            
            tdf.sort_values(by='strain_encoder', inplace=True)

            label = get_sample_label(trial_df=tdf)
            ax.plot(tdf['strain_encoder'], tdf['force'] - force_zero, label=label)

    force_unit = data_df['force_unit'].unique()[0]

    ax.grid()
    ax.set(xlabel='Strain', ylabel=f'Force [{force_unit}]',
        title=title)
    ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))

    infills = data_df['infill_density'].unique()
    perims = data_df['n_perimeters'].unique()

    fname = get_filename(title=title, infills=infills, perims=perims)
    fig.savefig(fname=fname, bbox_inches='tight', pad_inches=0.1)

    return


def thesis_plot(
        dfs: Dict[int, pd.DataFrame],
        title: str = 'Volumetric Strain vs. Engineering Strain',
        xlabel: str = 'Engineering Strain',
        ylabel: str = 'Volumetric Strain',
        small_font_size: str = 8,
        med_font_size: str = 10,
        big_font_size: str = 12,
        w: int = 8,
        h: int = 6
):  

    plt.style.use(['science'])
    fig, ax = plt.subplots()
    fig.set_size_inches(w, h)

    plt.rc('legend', fontsize=med_font_size)  # legend fontsize
    plt.rc('axes', titlesize=big_font_size)  # title fontsize

    for key, df in dfs.items():
        label = get_sample_label(id=key)
        ax.plot(df['x'], df['y'], label=label)

    ax.grid()
    ax.tick_params(axis='both', which='major', labelsize=small_font_size)
    ax.set_ylabel(ylabel, fontsize=med_font_size) 
    ax.set_xlabel(xlabel, fontsize=med_font_size) 
    ax.set(title=title)
    plt.legend(loc='upper center', 
               bbox_to_anchor=(0.48, -0.1), 
               fancybox=True, 
               shadow=True, 
               ncol=3)

    title = title.translate({ord(i): None for i in '. '})
    str_date = datetime.datetime.now().__str__().translate({ord(i): None for i in ':-. '})
    trial_ids = [str(x) for x in list(dfs.keys())]
    fname=f"{title}&infills{'_'.join(trial_ids)}&{str_date}.jpg"
    fname = "\\\\192.168.1.3\\main\\dn_plots\\" + fname
    fig.savefig(fname=fname, pad_inches=0.1)

    return


def trial_ids_by_infills(infills, session):
    query = session.query(Sample).filter(Sample.infill_density.in_(infills))
    df = pd.read_sql(sql=query.statement, con=session.bind)
    
    sample_ids = df['id'].unique()
    sample_ids = [int(x) for x in sample_ids]

    query = session.query(CompressionTrial).filter(CompressionTrial.sample_id.in_(sample_ids))
    df = pd.read_sql(sql=query.statement, con=session.bind)
    
    trial_ids = df['id'].unique()
    trial_ids = [int(x) for x in trial_ids]

    return trial_ids


def trial_ids_by_perims(perims, session):
    query = session.query(Sample).filter(Sample.n_perimeters.in_(perims))
    df = pd.read_sql(sql=query.statement, con=session.bind)
    
    sample_ids = df['id'].unique()
    sample_ids = [int(x) for x in sample_ids]

    query = session.query(CompressionTrial).filter(CompressionTrial.sample_id.in_(sample_ids))
    df = pd.read_sql(sql=query.statement, con=session.bind)
    
    trial_ids = df['id'].unique()
    trial_ids = [int(x) for x in trial_ids]

    return trial_ids


def trial_ids_by_testset(test_set_ids, session):

    query = session.query(CompressionTrial).filter(CompressionTrial.test_set_id.in_(test_set_ids))
    df = pd.read_sql(sql=query.statement, con=session.bind)
    
    trial_ids = df['id'].unique()
    trial_ids = [int(x) for x in trial_ids]

    return trial_ids


def main():

    Session = get_session(conn_str=CONN_STR)
    session = Session()

    test_set_ids = ['63d75ec4-c367-4e4a-8902-998b58ddb051']
    # test_set_ids = ['aa36a5ab-cd07-4b3b-962b-c5d9b1b3105f']
    trial_ids = trial_ids_by_testset(test_set_ids=test_set_ids, session=session)
    # ts_trial_ids += [93, 35, 98]

    # dfs = volstrain_vs_strain(trial_ids=ts_trial_ids, session=session)
    # thesis_plot(dfs=dfs,
    #             title='Volumetric Engineering Strain vs. Axial Engineering Strain',
    #             xlabel='Volumetric Engineering Strain',
    #             ylabel='Axial Engineering Strain')
    
    # dfs = force_vs_strain(trial_ids=ts_trial_ids, session=session)
    # thesis_plot(dfs=dfs,
    #             title='Force vs. Axial Engineering Strain',
    #             xlabel='Axial Engineering Strain',
    #             ylabel='Force [N]')
    
    dfs = force_normbyreldensity_vs_strain(trial_ids=trial_ids, session=session)
    thesis_plot(dfs=dfs,
                title='Normalized Force vs. Axial Engineering Strain',
                xlabel='Axial Engineering Strain',
                ylabel='Force [N], Normalized using Relatvie Density')




    # trial_ids = [93, 130, 35, 132, 133]
    
    # query = session.query(CompressionTrial, CompressionStep, Sample, ProcessedSTL).\
    #     filter(CompressionTrial.id.in_(trial_ids)).\
    #     join(CompressionStep, CompressionTrial.id == CompressionStep.compression_trial_id).\
    #     join(Sample, CompressionTrial.sample_id == Sample.id).\
    #     join(ProcessedSTL, CompressionStep.id == ProcessedSTL.compression_step_id)
    # df = pd.read_sql(sql=query.statement, con=session.bind)
    # df  = df.sort_values(by=['n_perimeters', 'infill_density'], ascending=[True, True])

    # force_vs_strain(data_df=df)
    # # new_plot(nofill_data_df=df.loc[df['id'] == 130], fill_data_df=df.loc[df['id'] == 35], both_data_df=df.loc[df['id'] == 93])
    # auxetic_vs_strain(data_df=df)

    # trial ids by infill
    # infills = [x / 10 for x in range(1, 10, 1)]
    # i_trial_ids = trial_ids_by_infills(infills=infills, session=session)

    # test_set_ids = ['63d75ec4-c367-4e4a-8902-998b58ddb051']
    # test_set_ids = ['aa36a5ab-cd07-4b3b-962b-c5d9b1b3105f']
    # ts_trial_ids = trial_ids_by_testset(test_set_ids=test_set_ids, session=session)
    # ts_trial_ids = [x for x in i_trial_ids if x in ts_trial_ids] + [93, 35, 98]

    # query = session.query(CompressionTrial, CompressionStep, Sample, ProcessedSTL).\
    #         filter(CompressionTrial.id.in_(ts_trial_ids)).\
    #         join(CompressionStep, CompressionTrial.id == CompressionStep.compression_trial_id).\
    #         join(Sample, CompressionTrial.sample_id == Sample.id).\
    #         join(ProcessedSTL, CompressionStep.id == ProcessedSTL.compression_step_id)
    # df = pd.read_sql(sql=query.statement, con=session.bind)
    # df  = df.sort_values(by=['n_perimeters', 'infill_density'], ascending=[True, True])
    # # force_vs_strain(data_df=df)
    # # auxetic_vs_strain(data_df=df)
    # # volume_vs_strain(data_df=df)
    # volstrain_vs_strain(df=df)

    session.close()

    # trial ids by perims
    # perims_groups = [[0], [1], [2]]

    # dfs = list()
    # for perims in perims_groups:
    #     p_trial_ids = trial_ids_by_perims(perims=perims, session=session)

    #     # infill and perim intersection
    #     trial_ids = [x for x in ts_trial_ids if x in p_trial_ids]
        
    #     query = session.query(CompressionTrial, CompressionStep, Sample, ProcessedSTL).\
    #         filter(CompressionTrial.id.in_(trial_ids)).\
    #         join(CompressionStep, CompressionTrial.id == CompressionStep.compression_trial_id).\
    #         join(Sample, CompressionTrial.sample_id == Sample.id).\
    #         join(ProcessedSTL, CompressionStep.id == ProcessedSTL.compression_step_id)
    #     df = pd.read_sql(sql=query.statement, con=session.bind)
    #     df  = df.sort_values(by=['n_perimeters', 'infill_density'], ascending=[True, True])
    #     dfs.append(df)
    #     # strain_energy_vs_infill(data_df=df)

    #     force_vs_strain(data_df=df)
    #     auxetic_vs_strain(data_df=df)
    #     volume_vs_strain(data_df=df)
    
    # strain_energy_vs_infill(data_dfs=dfs)

    return

if __name__ == '__main__':
    main()

