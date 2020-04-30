# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Helper module for computing training probabilities when modelling sessions."""

from collections import defaultdict
from typing import Tuple, Union

from ..utils.data_structures import StateMatrix


def compute_cmds_probs(
    seq1_counts: Union[StateMatrix, dict],
    seq2_counts: Union[StateMatrix, dict],
    unk_token: str = "##UNK##",
) -> Tuple[StateMatrix, StateMatrix]:
    """
    Computes command related probabilities.

    In particular, computes the probabilities for the individual commands, and also the
    probabilities for the transitions of commands.

    Parameters
    ----------
    seq1_counts: Union[StateMatrix, dict]
        individual command counts
    seq2_counts: Union[StateMatrix, dict]
        sequence command (length 2) counts
    unk_token: str
        dummy command to signify an unseen command (e.g. "##UNK##")

    Returns
    -------
    Tuple:
        individual command probabilities,
        sequence command (length 2) probabilities

    """
    total_cmds = sum(seq1_counts.values())

    prior_probs = defaultdict(lambda: 0)
    trans_probs = defaultdict(lambda: defaultdict(lambda: 0))

    # compute prior probs
    for cmd in seq1_counts:
        prior_probs[cmd] = seq1_counts[cmd] / total_cmds

    # compute trans probs
    for prev, currents in seq2_counts.items():
        for current in currents:
            trans_probs[prev][current] = seq2_counts[prev][current] / sum(
                seq2_counts[prev].values()
            )

    prior_probs = StateMatrix(states=prior_probs, unk_token=unk_token)
    trans_probs = StateMatrix(states=trans_probs, unk_token=unk_token)

    return prior_probs, trans_probs


def compute_params_probs(
    param_counts: Union[StateMatrix, dict],
    cmd_param_counts: Union[StateMatrix, dict],
    unk_token: str = "##UNK##",
) -> Tuple[StateMatrix, StateMatrix]:
    """
    Computes param related probabilities.

    In particular, computes the probabilities of the individual params, and also the probabilities
    of the params conditional on the command.

    Parameters
    ----------
    param_counts: Union[StateMatrix, dict]
        individual param counts
    cmd_param_counts: Union[StateMatrix, dict]
        param conditional on command counts
    unk_token: str
        dummy command to signify an unseen command (e.g. "##UNK##")

    Returns
    -------
    Tuple:
        individual param probabilities,
        param conditional on command probabilities

    """
    param_probs = defaultdict(lambda: 0)
    param_cond_cmd_probs = defaultdict(lambda: defaultdict(lambda: 0))

    for cmd, params in cmd_param_counts.items():
        n_param = sum(params.values())
        for param, count in params.items():
            param_cond_cmd_probs[cmd][param] = count / n_param

    tot_param = sum(param_counts.values())
    for param, count in param_counts.items():
        param_probs[param] = count / tot_param

    param_probs = StateMatrix(states=param_probs, unk_token=unk_token)
    param_cond_cmd_probs = StateMatrix(states=param_cond_cmd_probs, unk_token=unk_token)

    return param_probs, param_cond_cmd_probs


def compute_values_probs(
    value_counts: Union[StateMatrix, dict],
    param_value_counts: Union[StateMatrix, dict],
    unk_token: str = "##UNK##",
) -> Tuple[StateMatrix, StateMatrix]:
    """
    Computes value related probabilities.

    In particular, computes the probabilities of the individual values, and also the probabilities
    of the values conditional on the param.

    Parameters
    ----------
    value_counts: Union[StateMatrix, dict]
        individual value counts
    param_value_counts: Union[StateMatrix, dict]
        value conditional on param counts
    unk_token: str
        dummy command to signify an unseen command (e.g. "##UNK##")

    Returns
    -------
    Tuple:
        individual value probabilities,
        value conditional on param probabilities

    """
    value_probs = defaultdict(lambda: 0)
    value_cond_param_probs = defaultdict(lambda: defaultdict(lambda: 0))

    for param, values in param_value_counts.items():
        n_val = sum(values.values())
        for value, count in values.items():
            value_cond_param_probs[param][value] = count / n_val

    tot_val = sum(value_counts.values())
    for value, count in value_counts.items():
        value_probs[value] = count / tot_val

    value_probs = StateMatrix(states=value_probs, unk_token=unk_token)
    value_cond_param_probs = StateMatrix(
        states=value_cond_param_probs, unk_token=unk_token
    )

    return value_probs, value_cond_param_probs
