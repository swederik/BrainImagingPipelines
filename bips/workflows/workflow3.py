from .base import MetaWorkflow, load_config, register_workflow
import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
import os
from traits.api import HasTraits, Directory, Bool, Button
import traits.api as traits

desc = """
Task/Resting fMRI Quality Assurance workflow
============================================

"""
mwf = MetaWorkflow()
mwf.uuid = '5dd866fe8af611e1b9d5001e4fb1404c'
mwf.tags = ['task','fMRI','preprocessing','QA', 'resting']
mwf.uses_outputs_of = ['63fcbb0a890211e183d30023dfa375f2','7757e3168af611e1b9d5001e4fb1404c']
mwf.script_dir = 'u0a14c5b5899911e1bca80023dfa375f2'
mwf.help = desc
# config_ui
from workflow1 import get_dataflow

# define workflow
import nipype.interfaces.io as nio
from nipype.interfaces.freesurfer import ApplyVolTransform
from nipype.interfaces import freesurfer as fs
from nipype.interfaces.io import FreeSurferSource

from scripts.u0a14c5b5899911e1bca80023dfa375f2.QA_utils import (plot_ADnorm,
                                                                tsdiffana,
                                                                tsnr_roi,
                                                                combine_table,
                                                                art_output,
                                                                plot_motion,
                                                                plot_ribbon,
                                                                plot_anat,
                                                                overlay_new,
                                                                overlay_dB)

from ..utils.reportsink.io import ReportSink

totable = lambda x: [[x]]
to1table = lambda x: [x]
pickfirst = lambda x: x[0]

def sort(x):
    if isinstance(x,list):
        return sorted(x)
    else:
        return x

def get_config_params(subject_id, table):
        table.insert(0,['subject_id',subject_id])
        return table

def preproc_datagrabber(c,name='preproc_datagrabber'):
    # create a node to obtain the preproc files
    datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id','fwhm'],
                                                   outfields=['noise_components',
                                                              'motion_parameters',
                                                               'outlier_files',
                                                               'art_norm',
                                                               'tsnr',
                                                               'tsnr_detrended',
                                                               'tsnr_stddev',
                                                               'reg_file',
                                                               'motion_plots',
                                                               'mean_image',
                                                               'mask']),
                         name = name)
    datasource.inputs.base_directory = c.sink_dir
    datasource.inputs.template ='*'
    datasource.sort_filelist = True
    datasource.inputs.field_template = dict(motion_parameters='%s/preproc/motion/*.par',
                                            outlier_files='%s/preproc/art/*_outliers.txt',
                                            art_norm='%s/preproc/art/norm.*.txt',
                                            tsnr='%s/preproc/tsnr/*_tsnr.nii.gz',
                                            tsnr_detrended='%s/preproc/tsnr/*_detrended.nii.gz',
                                            tsnr_stddev='%s/preproc/tsnr/*tsnr_stddev.nii.gz',
                                            reg_file='%s/preproc/bbreg/*.dat',
                                            mean_image='%s/preproc/mean*/*.nii.gz',
                                            mask='%s/preproc/mask/*_brainmask.nii')
    datasource.inputs.template_args = dict(motion_parameters=[['subject_id']],
                                           outlier_files=[['subject_id']],
                                           art_norm=[['subject_id']],
                                           tsnr=[['subject_id']],
                                           tsnr_stddev=[['subject_id']],
                                           reg_file=[['subject_id']],
                                           mean_image=[['subject_id']],
                                           mask=[['subject_id']])
    return datasource


def start_config_table(c):
    table = []
    table.append(['TR',str(c.TR)])
    table.append(['Slice Order',str(c.SliceOrder)])
    table.append(['Realignment algorithm',c.motion_correct_node])
    if c.use_fieldmap:
        table.append(['Echo Spacing',str(c.echospacing)])
        table.append(['Fieldmap Smoothing',str(c.sigma)])
        table.append(['TE difference',str(c.TE_diff)])
    table.append(['Art: norm thresh',str(c.norm_thresh)])
    table.append(['Art: z thresh',str(c.z_thresh)])
    table.append(['Smoothing Algorithm',c.smooth_type])
    table.append(['fwhm',str(c.fwhm)])
    try:
        table.append(['Highpass cutoff',str(c.hpcutoff)])
    except:
        table.append(['highpass freq',str(c.highpass_freq)])
        table.append(['lowpass freq',str(c.lowpass_freq)])
    return table


def QA_workflow(c,QAc,name='QA'):
    """ Workflow that generates a Quality Assurance Report
    
    Parameters
    ----------
    name : name of workflow
    
    Inputs
    ------
    inputspec.subject_id :
    inputspec.config_params :
    inputspec.in_file :
    inputspec.art_file :
    inputspec.motion_plots :
    inputspec.reg_file :
    inputspec.tsnr_detrended :
    inputspec.tsnr :
    inputspec.tsnr_mean :
    inputspec.tsnr_stddev :
    inputspec.ADnorm :
    inputspec.TR :
    inputspec.sd : freesurfer subjects directory
    
    """
    
    # Define Workflow
        
    workflow =pe.Workflow(name=name)
    
    inputspec = pe.Node(interface=util.IdentityInterface(fields=['subject_id',
                                                                 'config_params',
                                                                 'in_file',
                                                                 'art_file',
                                                                 'motion_plots',
                                                                 'reg_file',
                                                                 'tsnr',
                                                                 'tsnr_mean',
                                                                 'tsnr_stddev',
                                                                 'ADnorm',
                                                                 'TR',
                                                                 'sd']),
                        name='inputspec')
    
    infosource = pe.Node(util.IdentityInterface(fields=['subject_id']),
                         name='subject_names')
    if QAc.test_mode:
        infosource.iterables = ('subject_id', [QAc.subjects[0]])
    else:
        infosource.iterables = ('subject_id', QAc.subjects)
    
    datagrabber = preproc_datagrabber(c)
    
    datagrabber.inputs.fwhm = c.fwhm
    
    orig_datagrabber = get_dataflow(c)
    
    workflow.connect(infosource, 'subject_id',
                     datagrabber, 'subject_id')
    
    workflow.connect(infosource, 'subject_id', orig_datagrabber, 'subject_id')
    
    workflow.connect(orig_datagrabber, 'func', inputspec, 'in_file')
    workflow.connect(infosource, 'subject_id', inputspec, 'subject_id')

    workflow.connect(datagrabber, ('outlier_files',sort), inputspec, 'art_file')
    workflow.connect(datagrabber, ('reg_file', sort), inputspec, 'reg_file')
    workflow.connect(datagrabber, ('tsnr',sort), inputspec, 'tsnr')
    workflow.connect(datagrabber, ('tsnr_stddev',sort), inputspec, 'tsnr_stddev')
    workflow.connect(datagrabber, ('art_norm',sort), inputspec, 'ADnorm')
    
    inputspec.inputs.TR = c.TR
    inputspec.inputs.sd = c.surf_dir
    
    # Define Nodes
    
    plot_m = pe.MapNode(util.Function(input_names=['motion_parameters'],
                                      output_names=['fname_t','fname_r'],
                                      function=plot_motion),
                        name="motion_plots",
                        iterfield=['motion_parameters'])
    
    workflow.connect(datagrabber,('motion_parameters', sort),plot_m,'motion_parameters')
    #workflow.connect(plot_m, 'fname',inputspec,'motion_plots')
    
    tsdiff = pe.MapNode(util.Function(input_names = ['img'], 
                                      output_names = ['out_file'], 
                                      function=tsdiffana), 
                        name='tsdiffana', iterfield=["img"])
                        
    art_info = pe.MapNode(util.Function(input_names = ['art_file'], 
                                      output_names = ['table','out'], 
                                      function=art_output), 
                        name='art_output', iterfield=["art_file"])
    
    fssource = pe.Node(interface = FreeSurferSource(),name='fssource')
    
    plotribbon = pe.Node(util.Function(input_names=['Brain'],
                                      output_names=['images'],
                                      function=plot_ribbon),
                        name="plot_ribbon")
    
    workflow.connect(fssource, 'ribbon', plotribbon, 'Brain')
    
    
    plotanat = pe.Node(util.Function(input_names=['brain'],
                                      output_names=['images'],
                                      function=plot_anat),
                        name="plot_anat")
        
    roidevplot = tsnr_roi(plot=False,name='tsnr_stddev_roi',roi=['all'],onsets=False)
    roidevplot.inputs.inputspec.TR = c.TR
    roisnrplot = tsnr_roi(plot=False,name='SNR_roi',roi=['all'],onsets=False)
    roisnrplot.inputs.inputspec.TR = c.TR
    
    workflow.connect(fssource, ('aparc_aseg', pickfirst), roisnrplot, 'inputspec.aparc_aseg')
    workflow.connect(fssource, ('aparc_aseg', pickfirst), roidevplot, 'inputspec.aparc_aseg')
    
    workflow.connect(infosource, 'subject_id', roidevplot, 'inputspec.subject')
    workflow.connect(infosource, 'subject_id', roisnrplot, 'inputspec.subject')
    
   
    tablecombine = pe.MapNode(util.Function(input_names = ['roidev',
                                                        'roisnr'],
                                         output_names = ['roisnr'], 
                                         function = combine_table),
                           name='combinetable', iterfield=['roidev','roisnr'])
    
    
    
    adnormplot = pe.MapNode(util.Function(input_names = ['ADnorm','TR','norm_thresh','out'], 
                                       output_names = ['plot'], 
                                       function=plot_ADnorm), 
                         name='ADnormplot', iterfield=['ADnorm','out'])
    adnormplot.inputs.norm_thresh = c.norm_thresh
    workflow.connect(art_info,'out',adnormplot,'out')
    
    convert = pe.Node(interface=fs.MRIConvert(),name='converter')
    
    voltransform = pe.MapNode(interface=ApplyVolTransform(),name='register',iterfield=['source_file'])
    
    overlaynew = pe.MapNode(util.Function(input_names=['stat_image','background_image','threshold',"dB"],
                                          output_names=['fnames'], function=overlay_dB), 
                                          name='overlay_new', iterfield=['stat_image'])
    overlaynew.inputs.dB = False
    overlaynew.inputs.threshold = 20
                                 
    overlaymask = pe.Node(util.Function(input_names=['stat_image','background_image','threshold'],
                                          output_names=['fnames'], function=overlay_new), 
                                          name='overlay_mask')
    overlaymask.inputs.threshold = 0
    
    workflow.connect(datagrabber, ('mean_image', sort), plotanat, 'brain')

    write_rep = pe.Node(interface=ReportSink(orderfields=['Introduction',
                                                          'in_file',
                                                          'config_params',
                                                          'Art_Detect',
                                                          'Mean_Functional',
                                                          'Ribbon',
                                                          'motion_plot_translations',
                                                          'motion_plot_rotations',
                                                          'tsdiffana',
                                                          'ADnorm',
                                                          'TSNR_Images',
                                                          'tsnr_roi_table']),
                                             name='report_sink')
    write_rep.inputs.Introduction = "Quality Assurance Report for fMRI preprocessing."
    write_rep.inputs.base_directory = os.path.join(QAc.sink_dir)
    write_rep.inputs.report_name = "Preprocessing_Report"
    write_rep.inputs.json_sink = QAc.json_sink
    workflow.connect(infosource,'subject_id',write_rep,'container')
    workflow.connect(plotanat, 'images', write_rep, "Mean_Functional")

    # Define Inputs
    
    convert.inputs.out_type = 'niigz'
    convert.inputs.in_type = 'mgz'
    
    # Define Connections
    workflow.connect(inputspec,'TR',adnormplot,'TR')
    workflow.connect(inputspec,'subject_id',fssource,'subject_id')
    workflow.connect(inputspec,'sd',fssource,'subjects_dir')
    workflow.connect(inputspec,'in_file',write_rep,'in_file')
    workflow.connect(inputspec,'art_file',art_info,'art_file')
    workflow.connect(art_info,('table',to1table), write_rep,'Art_Detect')
    workflow.connect(plot_m, 'fname_t',write_rep,'motion_plot_translations')
    workflow.connect(plot_m, 'fname_r',write_rep,'motion_plot_rotations')
    workflow.connect(inputspec,'in_file',tsdiff,'img')
    workflow.connect(tsdiff,"out_file",write_rep,"tsdiffana")
    workflow.connect(inputspec,('config_params',totable), write_rep,'config_params')
    workflow.connect(inputspec,'reg_file',roidevplot,'inputspec.reg_file')
    workflow.connect(inputspec,'tsnr_stddev',roidevplot,'inputspec.tsnr_file')
    workflow.connect(roidevplot,'outputspec.roi_table',tablecombine,'roidev')
    workflow.connect(inputspec,'reg_file',roisnrplot,'inputspec.reg_file')
    workflow.connect(inputspec,'tsnr',roisnrplot,'inputspec.tsnr_file')
    workflow.connect(roisnrplot,'outputspec.roi_table',tablecombine,'roisnr')
    workflow.connect(tablecombine, ('roisnr',to1table), write_rep, 'tsnr_roi_table')
    workflow.connect(inputspec,'ADnorm',adnormplot,'ADnorm')
    workflow.connect(adnormplot,'plot',write_rep,'ADnorm')
    workflow.connect(fssource,'orig',convert,'in_file')
    workflow.connect(convert,'out_file',voltransform,'target_file') 
    workflow.connect(inputspec,'reg_file',voltransform,'reg_file')
    workflow.connect(inputspec,'tsnr',voltransform, 'source_file')
    workflow.connect(plotribbon, 'images', write_rep, 'Ribbon')
    workflow.connect(voltransform,'transformed_file', overlaynew,'stat_image')
    workflow.connect(convert,'out_file', overlaynew,'background_image')
    
    workflow.connect(overlaynew, 'fnames', write_rep, 'TSNR_Images')
    
    workflow.write_graph()
    return workflow

    
def main(config_file):
    
    QA_config = load_config(config_file, create_config)
    if QA_config.task:
        from .workflow1 import create_config as prep_config
    else:
        from .workflow2 import create_config as prep_config

    c = load_config(QA_config.preproc_config, prep_config)
    a = QA_workflow(c,QA_config)
    a.base_dir = QA_config.working_dir
    if QA_config.test_mode:
        a.write_graph()

    a.inputs.inputspec.config_params = start_config_table(c)
    a.config = {'execution' : {'crashdump_dir' : QA_config.crash_dir}}
    if QA_config.run_using_plugin:
        a.run(plugin=QA_config.plugin,plugin_args=QA_config.plugin_args)
    else:
        a.run()

def create_view():
    from traitsui.api import View, Item, Group, CSVListEditor
    from traitsui.menu import OKButton, CancelButton
    view = View(Group(Item(name='uuid', style='readonly'),
                      Item(name='desc', style='readonly'),
                      label='Description', show_border=True),
                Group(Item(name='working_dir'),
                    Item(name='sink_dir'),
                    Item(name='crash_dir'),
                    Item(name='json_sink'),
                    label='Directories', show_border=True),
                Group(Item(name='run_using_plugin'),
                    Item(name='plugin', enabled_when="run_using_plugin"),
                    Item(name='plugin_args', enabled_when="run_using_plugin"),
                    Item(name='test_mode'),
                    label='Execution Options', show_border=True),
                Group(Item(name='subjects', editor=CSVListEditor()),
                    label='Subjects', show_border=True),
                Group(Item(name='preproc_config'),
                      Item(name='resting',enabled_when='not task'),
                      Item(name='task', enabled_when='not resting'),
                      label = 'Preprocessing Info'),
                buttons = [OKButton, CancelButton],
                resizable=True,
                width=1050)
    return view

class config(HasTraits):
    uuid = traits.Str(desc="UUID")
    desc = traits.Str(desc='Workflow description')
    # Directories
    working_dir = Directory(mandatory=True, desc="Location of the Nipype working directory")
    base_dir = Directory(exists=True, desc='Base directory of data. (Should be subject-independent)')
    sink_dir = Directory(mandatory=True, desc="Location where the BIP will store the results")
    field_dir = Directory(exists=True, desc="Base directory of field-map data (Should be subject-independent) \
                                                 Set this value to None if you don't want fieldmap distortion correction")
    crash_dir = Directory(mandatory=False, desc="Location to store crash files")
    json_sink = Directory(mandatory=False, desc= "Location to store json_files")
    surf_dir = Directory(mandatory=True, desc= "Freesurfer subjects directory")

    # Execution

    run_using_plugin = Bool(False, usedefault=True, desc="True to run pipeline with plugin, False to run serially")
    plugin = traits.Enum("PBS", "PBSGraph","MultiProc", "SGE", "Condor",
        usedefault=True,
        desc="plugin to use, if run_using_plugin=True")
    plugin_args = traits.Dict({"qsub_args": "-q many"},
        usedefault=True, desc='Plugin arguments.')
    test_mode = Bool(False, mandatory=False, usedefault=True,
        desc='Affects whether where and if the workflow keeps its \
                            intermediary files. True to keep intermediary files. ')
    # Subjects

    subjects= traits.List(traits.Str, mandatory=True, usedefault=True,
        desc="Subject id's. These subjects must match the ones that have been run in your preproc config")

    preproc_config = traits.File(desc="preproc config file")
    resting = traits.Bool(desc="True if running QA for resting preproc")
    task = traits.Bool(desc="True if running QA for task fmri preproc")

def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.desc = mwf.help
    return c


mwf.workflow_main_function = main
mwf.config_ui = create_config
mwf.config_view = create_view
register_workflow(mwf)