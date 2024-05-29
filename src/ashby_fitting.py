import glob
import os
import math

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from pathlib import Path
from scipy.optimize import differential_evolution
from compression_testing_data.meta import get_session
from compression_testing_data.models.samples import Sample 
from scipy.optimize import curve_fit
from compression_tester_controller.plots import get_trial_ids, get_trial_df, thesis_plot

CONN_STR = 'postgresql://domanlab:dn757657@192.168.1.3:5432/compression_testing'
Session = get_session(conn_str=CONN_STR)
session = Session()


HOME = Path.home()
DATA_PATH = HOME / Path('home/projects/ashby_foam_fiting/processed/raw')
DATA_PATH = Path('\\\\192.168.1.3\\Public\\old_testing_data')


def aggregate_data(d = DATA_PATH):
    """
    gotta modify this shit also since we messed up the area previously
    """ 
    all_df = pd.DataFrame()

    query = session.query(Sample).\
        filter(Sample.infill_pattern == 'gyroid')
    relp = pd.read_sql(sql=query.statement, con=session.bind)

    os.chdir(d)
    for file in glob.glob("*.txt"):
        file_info = file.__str__().split('_')
        infill = int(file_info[3])
        perims = int(file_info[4])
        
        if infill > 70:
            reldense = infill/100
        else:
            reldense = relp.loc[relp['infill_density'] == infill/100]['relative_density'].unique()[0]

        df =  pd.read_csv(file.__str__())
        df.drop(columns=['ts'], inplace=True)
        df['stress'] = df['stress'] * 4 / reldense
        df['infill'] = infill
        df['perims'] = perims
        df['relp'] = reldense

        if not all_df.empty:  
            all_df = pd.concat([df, all_df])
        else:
            all_df = df
    return all_df


def log_base_b_derivative2(x, a, b, k, c, d):
    return -a / ((x - c)**2 * np.log(b))


def log_base_b_derivative(x, a, b, k, c, d):
    return a / ((x - c) * np.log(b))


def log_base_b(x, a, b, k, c, d):
    arg = k * (x - c)
    if np.any(arg <= 0):
        return np.full_like(x, np.nan)
    return (a * (np.log(k * (x - c)) / np.log(b))) + d


def estimate_E(Es, dEdx, limit):
    
    dEdx_norm = (dEdx - np.min(dEdx)) / (np.max(dEdx) - np.min(dEdx))
    dEdx_norm_ = np.where(dEdx_norm > limit)
    # dEdx_norm_ = np.where(dEdx_norm < 0.1)

    # plt.plot(dEdx_norm)
    # plt.show()

    dEdx_minidx = np.min(dEdx_norm_)

    Eest = Es[dEdx_minidx]

    # plt.plot(Es)
    # plt.scatter(dEdx_minidx, Es[dEdx_minidx])
    # plt.show()

    return Eest

import warnings
def fit_data_and_decimate(x, y, n, infill):
    x = np.array(x)
    y = np.array(y)

    while True:

        params, params_covariance = curve_fit(log_base_b, x, y, p0=[1, 2, 1, 0, 0])
    
        x_new = np.linspace(x[0], x[len(x)-1], n)

        # z = np.polyfit(x, y, 20)
        # p = np.poly1d(z)
        # dp = np.polyder(p)
        # dpp = np.polyder(np.polyder(p))

        # TODO dynamic end point, roll back until fit is pretty good and no infinity in derivs

        y_new = log_base_b(x_new, *params)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                y_new_p = log_base_b_derivative(x_new, *params)
            except RuntimeWarning:
                print("terd")

            if w:
                for warning in w:
                    if issubclass(warning.category, RuntimeWarning):
                        print(f"Caught a RuntimeWarning: {warning.message}")
                        x = x[10:]
                        y = y[10:]
                continue

        y_new_pp = log_base_b_derivative2(x_new, *params)

        if np.any(y_new_p > 200) and infill < 20:
            print("fuck me")
            x = x[:-10]
            y = y[:-10]
        else:
            break

    
    # y_new = p(x_new)
    # y_new_p = dp(x_new)
    # y_new_pp = dpp(x_new)

    # plt.plot(x, y, '.', x_new, y_new, '-')
    # plt.show()

    # plt.plot(x_new, y_new_p)
    # plt.show()
    # plt.plot(x_new, y_new_pp)
    # plt.show()
    return x_new, y_new, y_new_p, y_new_pp


def compare_data_old_new(df_old, df_new, norm: bool = True):

    x_old = df_old['strain']
    y_old = df_old['stress']

    # old data is in stress, so we convert to force to compare to new data
    f = y_old * (10**2 * math.pi) * df_old['relp'].unique()[0]
    f = f - f.min()

    fnew = df_new['force'] - df_new['force'].min()
    x_new = df_new['strain_encoder']

    if norm:
        f_norm = (f - np.min(f)) / (np.max(f) - np.min(f))
        fnew_norm = (fnew - np.min(fnew)) / (np.max(fnew) - np.min(fnew))

        df1 = pd.DataFrame({'x': x_old, 'y': f_norm})
        df2 = pd.DataFrame({'x': x_new, 'y': fnew_norm})
    else:
        df1 = pd.DataFrame({'x': x_old, 'y': f})
        df2 = pd.DataFrame({'x': x_new, 'y': fnew})

    dfs = {
        1: df1,
        2: df2
    }

    thesis_plot(dfs=dfs,
            title='Lab Machine Force vs. Old Machine Force Data',
            xlabel='Axial Engineering Strain',
            ylabel='Force [N]',
            labels=['Old Data', 'New Data'])

    return


def get_poissons_ratio_cyl(
    df_new
):

    h0=df_new['height_enc'].unique()[0]
    vols=df_new['volume']
    espzs=df_new['strain_encoder']

    rads = (vols / (math.pi * h0 * (1 - espzs)))**0.5
    rad_strain = (rads - rads.min()) / rads.min()
    poi = rad_strain / espzs
        
    return poi[1:]


def calc_c4(relp: float, Es: float, sigmaEL: float):

    if relp <= .3:
        c4 = sigmaEL / ((relp**2) * ((1 + (relp**0.5))**2) * Es)
    else:
        c4 = sigmaEL / ((relp**2) * Es)

    return c4

from typing import List
def plot_ashby_C_consts(infills: List[int], perims: List[int], test_sets: List[str], n_fit = 1000):
    dfs = {}
    labels = []
    plot_type = []
    df = pd.DataFrame([])

    for perim in perims:
        for infill in infills:
            trial_ids = get_trial_ids(session=session, infills=[infill/100], perims=[perim], test_sets=test_sets)
            df_new = get_trial_df(session=session, trial_ids=trial_ids)
            df_new = df_new.loc[df_new['infill_pattern'] == 'gyroid']
            df_new = df_new.loc[df_new['created_at'] == df_new['created_at'].max()]

            df_old = all_df[(all_df['infill'] == infill) & (all_df['perims'] == perim) & (all_df['strain'] < strain_limit)]
            x = df_old['strain']
            y = df_old['stress']

            if not df_old.empty:
                x_fit, y_fit, y_fit_p, y_fit_pp = fit_data_and_decimate(x=x, y=y, n=n_fit, infill=infill)
                
                # get stuff for C1 -------------------
                Eest = estimate_E(Es=y_fit_p, dEdx=y_fit_pp, limit=0.94)
                Eest_idx = np.where(y_fit_p == Eest)
                espEL = x_fit[Eest_idx]
                sigmaEL = y_fit[Eest_idx]

                # usign the values from x and y (actual data) can result in poor fit but is true to
                # definition of E
                sigma0 = y[0]
                esp0 = x[0]

                # fits the line to the actual esimated espEL instead of using the 0ith values from
                # actual x and y, not grounded in reality
                sigma0 = y_fit[0]
                esp0 = x_fit[0]

                Eest = (sigmaEL - sigma0) / (espEL - esp0)
                b = y_fit[0] - (Eest * x_fit[0]) 

                
                p = int(Eest_idx[0] + (0.1 * n_fit))
                x_fit_Elin = x_fit[:p]
                y_Elin_fit = (x_fit_Elin * Eest) + b
                
                # plt.plot(x_fit, y_fit)
                # plt.plot(x_fit_Elin, y_Elin_fit, linestyle='dashed')
                # plt.scatter(x, y)
                # plt.scatter(espEL, thetaEL)
                # plt.show()

                # -------------- C3 --------------------
                poirs = get_poissons_ratio_cyl(df_new=df_new)
                c3 = np.mean(poirs)

                relp = df_old['relp'].unique()[0]
                cal_params = {
                    'E': Eest,
                    'sigmaEL': sigmaEL,
                    'espEL': espEL,
                    'relp': relp,
                    'perim': perim,
                    'c3': c3
                }

                df = pd.concat([df, pd.DataFrame(cal_params)], ignore_index=True)

    # C1 plotting  
    df['c1'] = ((df['E'] / df.loc[df['relp'] == 1]['E'].values) / 
                df['relp']**2)
    df['E*/Es'] = (df['E'] / df.loc[df['relp'] == 1]['E'].values)

    for perim in perims:
        df_plot = pd.DataFrame({
            'x': df.loc[df['perim'] == perim]['relp'],
            'y': df.loc[df['perim'] == perim]['E*/Es']
        })
        dfs[int(perim)] = df_plot

        labels.append(f"{perim} Perimeters")
        plot_type.append('scatter')
    
    ashby_x_C1 = np.array([i/100 for i in infills])
    ashby_y_C1 = ashby_x_C1
    dfs[100] = pd.DataFrame({'x': ashby_x_C1, 'y': ashby_y_C1})
    labels.append('Ashby Model')
    plot_type.append('dash')

    thesis_plot(dfs=dfs,
            title='C1 Analysis',
            xlabel='Relative Density',
            ylabel='E* / Es',
            labels=labels,
            plot_type=plot_type,
            y_log=True,
            x_log=True)
    
    # ------------- C2 plotting----------------
    dfs = {}
    for perim in perims:
        df_plot = pd.DataFrame({
            'x': df.loc[df['perim'] == perim]['relp'],
            'y': df.loc[df['perim'] == perim]['c3']
        })
        dfs[int(perim)] = df_plot

        labels.append(f"{perim} Perimeters")
        plot_type.append('scatter')
    
    ashby_x_C3 = np.array([i/100 for i in infills])
    ashby_y_C3 = 0.33
    dfs[100] = pd.DataFrame({'x': ashby_x_C3, 'y': ashby_y_C3})
    labels.append('Ashby Model')
    plot_type.append('dash')

    thesis_plot(dfs=dfs,
            title='C3 Analysis',
            xlabel='Relative Density',
            ylabel='v*',
            labels=labels,
            plot_type=plot_type,
            y_log=False,
            x_log=True)
    
    # ------------ C4 ---------------
    dfs = {}
    Es = df.loc[df['relp'] == 1]['E'].values
    df['c4'] = np.nan
    for idx in df.index:
        c4 = calc_c4(relp=df.iloc[idx]['relp'], Es=Es, sigmaEL=df.iloc[idx]['sigmaEL'])
        # c4p = d.get('thetaEL') * c1 / d.get('E')
        
        df.at[idx, 'c4'] = c4
    
    for perim in perims:
        df_plot = pd.DataFrame({
            'x': df.loc[df['perim'] == perim]['relp'],
            'y': df.loc[df['perim'] == perim]['c4']
        })
        dfs[int(perim)] = df_plot

        labels.append(f"{perim} Perimeters")
        plot_type.append('scatter')
    
    ashby_x_C4 = np.array([i/100 for i in infills])
    ashby_y_C4 = np.where(ashby_x_C4 <= 0.3, 0.05, 0.03)
    dfs[100] = pd.DataFrame({'x': ashby_x_C4, 'y': ashby_y_C4})
    labels.append('Ashby Model')
    plot_type.append('dash')

    thesis_plot(dfs=dfs,
            title='C4 Analysis',
            xlabel='Relative Density',
            ylabel='C4',
            labels=labels,
            plot_type=plot_type,
            y_log=False,
            x_log=True)

    pass 

        
if __name__ == '__main__':
    infills = [n * 10 for n in range(1, 11)]
    all_df = aggregate_data()
    cal_params = []
    c4s = []
    c3s = []
    c4ss = []
    strain_limit = 0.25
    n_fit = 1000

    
    # plot_ashby_C_consts(infills=infills, perims=[0, 1, 2], test_sets=['63d75ec4-c367-4e4a-8902-998b58ddb051'])    

    for infill in infills:
        trial_ids = get_trial_ids(session=session, infills=[infill/100], perims=[0], test_sets=['63d75ec4-c367-4e4a-8902-998b58ddb051'])
        df_new = get_trial_df(session=session, trial_ids=trial_ids)
        df_new = df_new.loc[df_new['infill_pattern'] == 'gyroid']
        df_new = df_new.loc[df_new['created_at'] == df_new['created_at'].max()]

        df_old = all_df[(all_df['infill'] == infill) & (all_df['perims'] == 0)]

        compare_data_old_new(df_new=df_new, df_old=df_old)