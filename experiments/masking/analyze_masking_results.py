from pathlib import Path
import os
import pickle
import pandas as pd
import numpy as np
from sklearn.metrics import f1_score
import seaborn as sns
import matplotlib.pyplot as plt

PROJECT_DIR = Path(__file__).parent.parent.parent
# RESULTS_DIR = os.path.join(PROJECT_DIR, 'results', 'inference', 'syn4')
# RESULTS_DIR = os.path.join(PROJECT_DIR, 'results', 'inference', 'syn5')
RESULTS_DIR = os.path.join(PROJECT_DIR, 'results', 'masking')


def load_results(files):

    columns = ['model', 'data', 'tok', 'mask', 'topk_mask', 'preds', 'labels', 'masked_tokens', 'masked_records']
    data = []
    for f in files:
        file_name = f.split(os.sep)[-1]
        if not file_name.startswith('INFERENCE'):
            continue

        row = pickle.load(open(f, 'rb'))
        if file_name.startswith('INFERENCE_SBERT'):
            row['model'] = 'SBERT'
        elif file_name.startswith('INFERENCE_DITTO'):
            row['model'] = 'Ditto'
        elif file_name.startswith('INFERENCE_SUPCON'):
            row['model'] = 'SupCon'
        else:
            row['model'] = 'BERT'
        data.append(row)

    out = pd.DataFrame(data, columns=columns)

    out = out[out['topk_mask'].isin([3, np.nan])]
    # out = out[out['topk_mask'].isin([5, np.nan])]

    # SYN
    # out = out[out['mask'].isin(["off", "maskSyn", "random"])]
    # SEM
    # out = out[out['mask'].isin(["off", "maskSem", "random"])]
    # SYM + SEM
    out = out[out['mask'].isin(["off", "maskSyn", "maskSem", "random"])]

    out = out.reset_index(drop=True)

    return out


def compute_performance(results):

    f1_list = [None for _ in range(len(results))]
    mask_perc_list = [None for _ in range(len(results))]
    counts = [None for _ in range(len(results))]
    true_f1_list = [None for _ in range(len(results))]
    true_mask_perc_list = [None for _ in range(len(results))]
    true_counts = [None for _ in range(len(results))]

    for dataset, df_dataset in results.groupby('data'):

        # Find the common masks: loop over the results with different model/tok/topk/mask and find the common records
        # where all these configurations are defined (use the mask to know which records have been masked for each conf
        # and take the records where all the mask elements are true)
        common_mask = None
        common_true_mask = None
        for ix, row in df_dataset.iterrows():

            if row['mask'] == 'off':
                continue

            mask = row['masked_records']
            true_mask = row['masked_tokens'] >= row['topk_mask']

            if common_mask is None:
                common_mask = mask
                common_true_mask = true_mask
            else:
                common_mask &= mask
                common_true_mask &= true_mask

        # Calculate some metrics on the records that have been masked
        for ix, row in df_dataset.iterrows():
            preds = row['preds'].flatten()
            labels = row['labels']
            joint_true_mask = common_mask & common_true_mask

            # Calculate some metrics on the records that have been masked (also if the number of masked words is less
            # than topk)
            unmask_preds = preds[common_mask]
            unmask_labels = labels[common_mask]
            f1 = f1_score(unmask_labels, unmask_preds)
            mask_perc = (len(unmask_preds) / len(preds)) * 100
            f1_list[ix] = f1
            mask_perc_list[ix] = mask_perc
            counts[ix] = len(unmask_preds)

            # Calculate some metrics on the records that have been masked (where exactly topk words have been masked)
            true_unmask_preds = preds[joint_true_mask]
            true_unmask_labels = labels[joint_true_mask]
            true_f1 = f1_score(true_unmask_preds, true_unmask_labels)
            true_mask_perc = (joint_true_mask.sum() / len(joint_true_mask)) * 100
            true_f1_list[ix] = true_f1
            true_mask_perc_list[ix] = true_mask_perc
            true_counts[ix] = joint_true_mask.sum()

    # Save the metrics in the DataFrame
    out_results = results.copy()
    out_results['f1'] = f1_list
    out_results['mask_perc'] = mask_perc_list
    out_results['count'] = counts
    out_results['true_f1'] = true_f1_list
    out_results['true_mask_perc'] = true_mask_perc_list
    out_results['true_count'] = true_counts

    return out_results


def compute_performance_OLD(results):
    f1_list = []
    mask_perc_list = []
    counts = []
    true_f1_list = []
    true_mask_perc_list = []
    true_counts = []
    for ix, row in results.iterrows():
        preds = np.squeeze(row['preds'], 1)
        labels = row['labels']
        mask = row['masked_records']
        true_mask = row['masked_tokens'] >= row['topk_mask']
        joint_true_mask = mask & true_mask

        unmask_preds = preds[mask]
        unmask_labels = labels[mask]
        f1 = f1_score(unmask_labels, unmask_preds)
        mask_perc = (mask.sum() / len(mask)) * 100
        f1_list.append(f1)
        mask_perc_list.append(mask_perc)
        counts.append(mask.sum())

        true_unmask_preds = preds[joint_true_mask]
        true_unmask_labels = labels[joint_true_mask]
        true_f1 = f1_score(true_unmask_preds, true_unmask_labels)
        true_mask_perc = (joint_true_mask.sum() / len(joint_true_mask)) * 100
        true_f1_list.append(true_f1)
        true_mask_perc_list.append(true_mask_perc)
        true_counts.append(joint_true_mask.sum())

    out_results = results.copy()
    out_results['f1'] = f1_list
    out_results['mask_perc'] = mask_perc_list
    out_results['count'] = counts
    out_results['true_f1'] = true_f1_list
    out_results['true_mask_perc'] = true_mask_perc_list
    out_results['true_count'] = true_counts

    return out_results


def save_masking_pair_plot(data):
    fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(12, 4), sharey=True)
    axes = axes.flat
    df_sent = data[data['encoding'] == 'sent-pair']
    sns.boxplot(x="masking", hue="model", y="F1", data=df_sent, ax=axes[0])
    axes[0].set_title('Sent-pair', fontsize=14)
    axes[0].get_legend().remove()
    axes[0].tick_params(axis='both', which='major', labelsize=14)
    axes[0].tick_params(axis='both', which='minor', labelsize=14)
    axes[0].set_xlabel('masking', fontsize=14)
    axes[0].set_ylabel('F1', fontsize=14)

    df_attr = data[data['encoding'] == 'attr-pair']
    sns.boxplot(x="masking", hue="model", y="F1", data=df_attr, ax=axes[1])
    axes[1].set_title('Attr-pair', fontsize=14)
    axes[1].get_legend().remove()
    axes[1].get_yaxis().set_visible(False)
    axes[1].tick_params(axis='both', which='major', labelsize=14, left=False)
    axes[1].tick_params(axis='both', which='minor', labelsize=14)
    axes[1].set_xlabel('masking', fontsize=14)

    handles, labels = axes[1].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=2)

    plt.tight_layout()
    plt.savefig("sbert_masking_all.pdf")


def save_masking_plot(data, key):
    sel_data = data[data['encoding'] == key]

    # Define a custom order
    model_order_map = {'BERT': 0, 'SBERT': 1, 'Ditto': 2, 'SupCon': 3}
    masking_order_map = {'off': 0, 'semantic': 1, 'syntax': 2, "random": 3}
    sel_data['model_order'] = sel_data['model'].map(model_order_map)
    sel_data['masking_order'] = sel_data['masking'].map(masking_order_map)
    sel_data = sel_data.sort_values(['model_order', 'masking_order'])
    sel_data = sel_data.drop(['model_order', 'masking_order'], axis=1)

    ax = sns.boxplot(x="masking", hue="model", y="F1", data=sel_data)
    ax.tick_params(axis='both', which='major', labelsize=14, left=False)
    ax.tick_params(axis='both', which='minor', labelsize=14)
    ax.set_xlabel('masking', fontsize=14)
    ax.set_ylabel('F1', fontsize=14)
    fig = plt.gcf()
    fig.set_size_inches(6, 4)
    plt.tight_layout()
    plt.savefig("em_masking.pdf")


if __name__ == '__main__':
    files = [os.path.join(RESULTS_DIR, f) for f in os.listdir(RESULTS_DIR) if
             os.path.isfile(os.path.join(RESULTS_DIR, f))]
    results = load_results(files)
    perf = compute_performance(results)

    # Select the performance only for the dataset with at least 100 masked records
    target_datasets = perf[perf['true_count'] > 100]['data'].unique()
    perf = perf[perf['data'].isin(target_datasets)]
    perf = perf[['model', 'data', 'tok', 'mask', 'topk_mask', 'true_f1']]

    perf = perf.rename(columns={'tok': 'encoding', 'mask': 'masking', 'true_f1': 'F1'})
    perf = perf[['model', 'encoding', 'masking', 'F1']]

    perf['masking'] = perf['masking'].map(
        {'maskSem': 'semantic', 'maskSyn': 'syntax', 'off': 'off', 'random': 'random'}
    )

    out_perf = perf[perf['masking'] == 'off'].copy()
    out_perf = pd.concat((out_perf, perf[perf['masking'] != 'off'].copy()))

    save_masking_plot(out_perf, 'sent_pair')

    perf.to_csv(os.path.join(RESULTS_DIR, 'report.csv'))
