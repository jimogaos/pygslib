# -*- coding: utf-8 -*-
#!/usr/bin/env python

# using naming on http://www.gslib.com/gslib_help/programs.html
import subprocess
import copy
import pandas as pd
import pygslib
import numpy as np
import os
import matplotlib.pyplot as plt

__gamv_par = \
"""                  Parameters for GAMV
                  *******************

START OF PARAMETERS:
{datafl}                          -file with data
{icolx} {icoly} {icolz}           -   columns for X, Y, Z coordinates
{nvar} {ivar_}                    - number of variables: column numbers
{tmin} {tmax}                     - trimming limits
{outfl}                           -file for variogram output
{nlag}                            -number of lags
{xlag}                            -lag separation distance
{xltol}                           -lag tolerance
{ndir}                            -number of directions
{ivdir_}                          -azm,atol,bandh,dip,dtol,bandv (array with shape [ndir,6])
{standardize}                     -standardize sill? (0=no, 1=yes)
{nvarg}                           -number of variograms
{ivpar_}                          -tail, head, variogram type, cut (array with shape [nvarg,4])


cut[i] is only required if ivtype[i] == 9 or == 10

"""

def gamv(parameters, gslib_path = None, silent = False):
    """gamv(parameters, gslib_path = None)

    Funtion to calculate experimental variogram with scattered data using
    the gamv.exe external gslib program.

    Parameters
    ----------
    parameters : dict
        dictionary with parameters
    gslib_path : string (default None)
        absolute or relative path to gslib excecutable programs
    silent: boolean
        if true external GSLIB stdout text is printed

    Returns
    ------
    pandas.DataFrame with variograms

    Example
    --------
    TODO:

    Notes
    ------
    The dictionary with parameters may be as follows::


        parameters = {
            'datafl' : str or, None, or numpy,     # path to file, or none (to use '_xxx_.in') or numpy array (with columns [x,y])
            'icolx'  : int,                        # columns for X, Y, Z coordinates
            'icoly'  : int,
            'icolz'  : int,
            'ivar'   : 1D array of int,            # variables column numbers to be used in ivtail and ivhead,
            'tmin'   : float,                      # trimming limits min and max (raws out of this range will be ignored)
            'tmax'   : float,
            'outfl': str or None,                   # path to the output file or None (to use '_xxx_.out')
            'nlag'   : int,                         # number of lags
            'xlag'   : float,                       # lag separation distance
            'xltol'  : float,                       # lag tolerance
            'ivdir'  : 2D array of floats           # azm,atol,bandh,dip,dtol,bandv (array with shape [ndir,6])
            'standardize': int,                     # standardize sill? (0=no, 1=yes)
            'ivpar': 2D array of int}               # tail, head, variogram type, and cut (with shape [nvarg,4])

            vg type  1 = traditional semivariogram
                     2 = traditional cross semivariogram
                     3 = covariance
                     4 = correlogram
                     5 = general relative semivariogram
                     6 = pairwise relative semivariogram
                     7 = semivariogram of logarithms
                     8 = semimadogram
                     9 = indicator semivariogram - continuous
                     10= indicator semivariogram - categorical

    see http://www.gslib.com/gslib_help/gamv.html for more information

    """

    if gslib_path is None:
        if os.name == "posix":
            gslib_path = '~/gslib/gamv'
        else:
            gslib_path = 'c:\\gslib\\gamv.exe'

    mypar = copy.deepcopy(parameters)

    # handle the case where input is an array an not a file
    if isinstance(parameters['datafl'], np.ndarray):
        assert (parameters['datafl'].ndim==2)

        mypar['datafl']='_xxx_.in'
        mypar['icolx']= 1
        mypar['icoly']= 2
        mypar['icolz']= 3
        mypar['ivar'] = np.arange(4,parameters['datafl'].shape[1]+1,dtype=int)

        with open('_xxx_.in',"w") as f:
            f.write('temp file '+'\n')
            f.write('{}'.format(parameters['datafl'].shape[1])+'\n')
            f.write('x\n')
            f.write('y\n')
            f.write('z\n')
            for i in range(3,parameters['datafl'].shape[1]):
                f.write('v{}\n'.format(i-2))
            np.savetxt(f,parameters['datafl'])
    elif parameters['datafl'] is None:
        mypar['datafl']='_xxx_.in'

    if mypar['outfl'] is None:
        mypar['outfl'] = '_xxx_.out'

    # handle parameter arrays
    ivpar = np.array (mypar['ivpar'])
    ivdir = np.array (mypar['ivdir'])

    assert (ivpar.shape[1]==4)
    assert (ivdir.shape[1]==6)

    assert (all([i<=len(mypar['ivar']) for i in ivpar[:,0]]))  # head variable
    assert (all([i<=len(mypar['ivar']) for i in ivpar[:,1]]))  # tail variable
    assert (set(ivpar[:,2]).issubset(set([1,2,3,4,5,6,7,8,9,10]))) # ivtype
    for i in range(ivpar.shape[0]):
        if ivpar[i,2]<9:
            ivpar[i,3] = None
        else:
            if ivpar[i,3]==None:
                raise NameError('gslib varmap Error inparameter file: cut[{}]=None'.format(i))


    # prepare parameter file and save it
    mypar['nvar'] = len(mypar['ivar'])
    mypar['ivar_'] = ' '.join(map(str, mypar['ivar'])) # array to string

    mypar['nvarg'] = ivpar.shape[0]
    mypar['ivpar_'] = pd.DataFrame.to_string(pd.DataFrame(ivpar),index= False, header=False) # array to string

    mypar['ndir'] = ivdir.shape[0]
    mypar['ivdir_'] = pd.DataFrame.to_string(pd.DataFrame(ivdir),index= False, header=False) # array to string

    par = __gamv_par.format(**mypar)
    print (par)
    fpar ='_xxx_.par'
    with open(fpar,"w") as f:
        f.write(par)

    # call pygslib
    # this construction can be used in a loop for parallel execution
    p=subprocess.Popen([gslib_path, fpar],
                       stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    result = p.returncode
    p.wait()

    if p.returncode!=0:
        raise NameError('gslib declus NameError' + str(stderr.decode('utf-8')))

    if ~silent:
        try:
            print (stdout.decode('utf-8'))
        except:
            print (stdout)

    # put results in pandas
    nvarg = mypar['nvarg']
    ndir = mypar['ndir']
    nlag = mypar['nlag'] + 2

    ignore = np.arange(0,nvarg*ndir*nlag+ndir*nvarg,nlag+1) # list to ignore variogram headers
    # a) read resulting file
    if any(ivpar[:,2]==4):
        vg = pd.read_csv(mypar['outfl'],
                        header=None,
                        skiprows = ignore,
                        delim_whitespace= True,
                        names = ['Lag',
                                'average separation',
                                'var funct',
                                'number of pairs',
                                'mean on tail',
                                'mean on head',
                                'variance tail',
                                'variance head'])
    else:
        vg = pd.read_csv(mypar['outfl'],
                        header=None,
                        skiprows = ignore,
                        delim_whitespace= True,
                        names = ['Lag',
                                'average separation',
                                'var funct',
                                'number of pairs',
                                'mean on tail',
                                'mean on head'])
    # b) add extra variables from headers
    vg['Variogram'] = np.repeat(range(nvarg), ndir*nlag) # variogram number = row index on parameter['ivpar']
    vg['Direction'] = np.tile(np.repeat(range(ndir), nlag),nvarg)
    vg['tail'] = 0
    vg['head'] = 0
    vg['type'] = 0
    vg['cut'] = None
    for i in range(len(parameters['ivpar'])):
        vg.loc[vg['Variogram']==i,'tail'] = parameters['ivpar'][i][0]
        vg.loc[vg['Variogram']==i, 'head'] = parameters['ivpar'][i][1]
        vg.loc[vg['Variogram']==i, 'type'] = parameters['ivpar'][i][2]
        vg.loc[vg['Variogram']==i,'cut'] = parameters['ivpar'][i][3]

    # clean a bit zeros and variogram at distance zero
    vg.loc[vg['number of pairs']==0,['var funct','mean on tail','mean on head']]=None
    vg.loc[vg['average separation']==0,'var funct']=None
    vg = vg.set_index(['Variogram', 'Direction', 'Lag'])
    # prepare figure

    # TODO add variance line

    fig, ax = plt.subplots(figsize=(8,6))
    for i in vg.index.levels[0]:
        for j in vg.index.levels[1]:
            vg.loc[i,j].plot(kind='line', x= 'average separation', y = 'var funct', ax=ax, label = 'v{} d{}'.format(i,j))

    return vg, fig, ax
