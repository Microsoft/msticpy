from collections import defaultdict
from typing import Tuple, List, Union
import numpy as np

from msticpy.analysis.anomalous_sequence.utils.data_structures import StateMatrix, Cmd


def compute_counts(
    sessions: List[List[Cmd]],
    start_token: str = "##START##",
    end_token: str = "##END##",
    unk_token: str = "##UNK##",
) -> Tuple[
    StateMatrix, StateMatrix, StateMatrix, StateMatrix, StateMatrix, StateMatrix
]:
    """
    computes counts of individual commands and of sequences of two commands. It also computes the counts of
    individual params as well as counts of params conditional on the command. It also computes the counts of
    individual values as well as counts of values conditional on the param.

    Laplace smoothing is applied to the counts.
    This is so we shift some of the probability mass from the very probable commands/params/values to the unseen and
    very unlikely commands/params/values.
    The `unk_token` means we can handle unseen commands, params, values, sequences of commands

    Parameters
    ----------
    sessions: List[List[Cmd]]
        each session is a list of the Cmd datatype. Where the Cmd datatype has a name attribute (command name) and a
        params attribute (dict with the params and values associated with the command)
        an example session:
            [Cmd(name='Set-User', params={'Identity': 'blahblah', 'Force': 'true'}), Cmd(name='Set-Mailbox',
            params={'Identity': 'blahblah', 'AuditEnabled': 'false'})]
    start_token: str
        dummy command to signify the start of a session (e.g. "##START##")
    end_token: str
        dummy command to signify the end of a session (e.g. "##END##")
    unk_token: str
        dummy command to signify an unseen command (e.g. "##UNK##")

    Returns
    -------
    tuple of counts:
        individual command counts,
        sequence command (length 2) counts,
        individual param counts,
        param conditional on command counts
        individual value counts,
        value conditional on param counts
    """

    seq1_counts = defaultdict(lambda: 0)
    seq2_counts = defaultdict(lambda: defaultdict(lambda: 0))

    param_counts = defaultdict(lambda: 0)
    cmd_param_counts = defaultdict(lambda: defaultdict(lambda: 0))

    value_counts = defaultdict(lambda: 0)
    param_value_counts = defaultdict(lambda: defaultdict(lambda: 0))

    for session in sessions:
        prev = start_token
        seq1_counts[prev] += 1
        for cmd in session:
            seq1_counts[cmd.name] += 1
            seq2_counts[prev][cmd.name] += 1
            prev = cmd.name
            for p, v in cmd.params.items():
                param_counts[p] += 1
                value_counts[v] += 1
                cmd_param_counts[cmd.name][p] += 1
                param_value_counts[p][v] += 1
        seq2_counts[prev][end_token] += 1
        seq1_counts[end_token] += 1

    # apply laplace smoothing for the cmds
    cmds = list(seq1_counts.keys()) + [unk_token]
    for cmd1 in cmds:
        for cmd2 in cmds:
            if cmd1 != end_token and cmd2 != start_token:
                seq1_counts[cmd1] += 1
                seq2_counts[cmd1][cmd2] += 1
                seq1_counts[cmd2] += 1

    # apply laplace smoothing for the params
    params = list(param_counts.keys()) + [unk_token]
    for cmd in cmds:
        for param in params:
            if param in cmd_param_counts[cmd] or param == unk_token:
                param_counts[param] += 1
                cmd_param_counts[cmd][param] += 1

    # apply laplace smoothing for the values
    values = list(value_counts.keys()) + [unk_token]
    for param in params:
        for value in values:
            if value in param_value_counts[param] or value == unk_token:
                value_counts[value] += 1
                param_value_counts[param][value] += 1

    seq1_counts = StateMatrix(states=seq1_counts, unk_token=unk_token)
    seq2_counts = StateMatrix(states=seq2_counts, unk_token=unk_token)
    param_counts = StateMatrix(states=param_counts, unk_token=unk_token)
    cmd_param_counts = StateMatrix(states=cmd_param_counts, unk_token=unk_token)
    value_counts = StateMatrix(states=value_counts, unk_token=unk_token)
    param_value_counts = StateMatrix(states=param_value_counts, unk_token=unk_token)

    return (
        seq1_counts,
        seq2_counts,
        param_counts,
        cmd_param_counts,
        value_counts,
        param_value_counts,
    )


def get_params_to_model_values(
    param_counts: Union[StateMatrix, dict], param_value_counts: Union[StateMatrix, dict]
) -> set:
    """
    uses rough heuristics to determine whether the values of each param are categorical or arbitrary strings.

    Parameters
    ----------
    param_counts: Union[StateMatrix, dict]
        counts of each of the individual params
    param_value_counts: Union[StateMatrix, dict]
        counts of each value conditional on the params

    Returns
    -------
    set of params which have been determined to be categorical
    """
    param_stats = [
        (param, len(vals), param_counts[param], 100 * len(vals) / param_counts[param])
        for param, vals in param_value_counts.items()
    ]

    modellable_params = [
        param[0]
        for param in param_stats
        if param[1] <= 20 and param[2] >= 20 and param[3] <= 10
    ]

    return set(modellable_params)


def compute_prob_setofparams_given_cmd(
    cmd: str,
    params_with_vals: dict,
    param_cond_cmd_probs: Union[StateMatrix, dict],
    value_cond_param_probs: Union[StateMatrix, dict],
    modellable_params: Union[set, list],
    use_geo_mean: bool = True,
) -> float:
    """
    Given a command and its accompanying params and values, compute the probabilty of that set of params and values
    appearing, conditional on the command

    Parameters
    ----------
    cmd: str
        name of command (e.g. for Exchange powershell commands: "Set-Mailbox")
    params_with_vals: dict
        dict of accompanying params and values for the cmd
        e.g for Exchange powershell commands:
            {'Identity': 'an_identity' , 'ForwardingEmailAddress': 'email@email.com'}
    param_cond_cmd_probs: Union[StateMatrix, dict]
        computed probabilities of params conditional on the command
    value_cond_param_probs: Union[StateMatrix, dict]
        computed probabilities of values conditional on the param
    modellable_params: set
        set of params for which we will also include the probabilties of their values in the
        calculation of the likelihood
    use_geo_mean: bool
        if True, then the likelihood will be raised to the power of (1/K) where K is the number of
        distinct params which appeared for the given `cmd` across our training set + the number of values which we
        included in the modelling for this cmd.
        Note:
            Some commands may have more params set in general compared with other commands. It can be useful to use the
            geo mean so that you can compare this probability across different commands with differing number of params

    Returns
    -------
    computed probability
    """
    if len(params_with_vals) == 0:
        return 1
    ref_cmd = param_cond_cmd_probs[cmd]
    prob = 1
    num = 0
    for param, p1 in ref_cmd.items():
        if param in params_with_vals:
            prob *= p1
            if param in modellable_params:
                num += 1
                v = params_with_vals[param]
                prob *= value_cond_param_probs[param][v]
        else:
            prob *= 1 - p1
    if use_geo_mean:
        k = len(ref_cmd) + num
        if k > 0:
            prob = prob ** (1 / k)

    return prob


def compute_likelihood_window(
    window: List[Cmd],
    prior_probs: Union[StateMatrix, dict],
    trans_probs: Union[StateMatrix, dict],
    param_cond_cmd_probs: Union[StateMatrix, dict],
    value_cond_param_probs: Union[StateMatrix, dict],
    modellable_params: set,
    use_start_token: bool,
    use_end_token: bool,
    start_token: str = None,
    end_token: str = None,
) -> float:
    """
    computes the likelihood of the input `window`

    Parameters
    ----------
    window: List[Cmd]
        part or all of a session, where a session is a list the Cmd datatype
        an example session:
            [Cmd(name='Set-User', params={'Identity': 'blahblah', 'Force': 'true'}), Cmd(name='Set-Mailbox',
            params={'Identity': 'blahblah', 'AuditEnabled': 'false'})]
    prior_probs: Union[StateMatrix, dict]
        computed probabilities of individual commands
    trans_probs: Union[StateMatrix, dict]
        computed probabilities of sequences of commands (length 2)
    param_cond_cmd_probs: Union[StateMatrix, dict]
        computed probabilities of the params conditional on the commands
    value_cond_param_probs: Union[StateMatrix, dict]
        computed probabilities of the values conditional on the params
    modellable_params: set
        set of params for which we will also include the probabilties of their values in the calculation of the
        likelihood
    use_start_token: bool
        if set to True, the start_token will be prepended to the window before the likelihood
        calculation is done
    use_end_token: bool
        if set to True, the end_token will be appended to the window before the likelihood
        calculation is done
    start_token: str
        dummy command to signify the start of the session (e.g. "##START##")
    end_token: str
        dummy command to signify the end of the session (e.g. "##END##")

    Returns
    -------
    likelihood of the window
    """
    if use_start_token:
        assert start_token is not None
    if use_end_token:
        assert end_token is not None

    n = len(window)
    if n == 0:
        return np.nan
    prob = 1

    cur_cmd = window[0].name
    params = window[0].params
    param_vals_prob = compute_prob_setofparams_given_cmd(
        cmd=cur_cmd,
        params_with_vals=params,
        param_cond_cmd_probs=param_cond_cmd_probs,
        value_cond_param_probs=value_cond_param_probs,
        modellable_params=modellable_params,
        use_geo_mean=True,
    )

    if use_start_token:
        prob *= trans_probs[start_token][cur_cmd] * param_vals_prob
    else:
        prob *= prior_probs[cur_cmd] * param_vals_prob

    for i, cmdparam in enumerate(window[1:]):
        prev, cur = window[i - 1], window[i]
        prev_cmd, cur_cmd = prev.name, cur.name
        prev_par, cur_par = prev.params, cur.params
        prob *= trans_probs[prev_cmd][cur_cmd]
        param_vals_prob = compute_prob_setofparams_given_cmd(
            cmd=cur_cmd,
            params_with_vals=cur_par,
            param_cond_cmd_probs=param_cond_cmd_probs,
            value_cond_param_probs=value_cond_param_probs,
            modellable_params=modellable_params,
            use_geo_mean=True,
        )
        prob *= param_vals_prob

    if use_end_token:
        prob *= trans_probs[cur_cmd][end_token]

    return prob


def compute_likelihood_windows_in_session(
    session: List[Cmd],
    prior_probs: Union[StateMatrix, dict],
    trans_probs: Union[StateMatrix, dict],
    param_cond_cmd_probs: Union[StateMatrix, dict],
    value_cond_param_probs: Union[StateMatrix, dict],
    modellable_params: set,
    window_len: int,
    use_start_end_tokens: bool,
    start_token: str = None,
    end_token: str = None,
    use_geo_mean: bool = False,
) -> List[float]:
    """
    computes the likelihoods of a sliding window of length `window_len` throughout the session

    Parameters
    ----------
    session: List[Cmd]
        list of Cmd datatype
        an example session:
            [Cmd(name='Set-User', params={'Identity': 'blahblah', 'Force': 'true'}), Cmd(name='Set-Mailbox',
            params={'Identity': 'blahblah', 'AuditEnabled': 'false'})]
    prior_probs: Union[StateMatrix, dict]
        computed probabilities of individual commands
    trans_probs: Union[StateMatrix, dict]
        computed probabilities of sequences of commands (length 2)
    param_cond_cmd_probs: Union[StateMatrix, dict]
        computed probabilities of the params conditional on the commands
    value_cond_param_probs: Union[StateMatrix, dict]
        computed probabilities of the values conditional on the params
    modellable_params: set
        set of params for which we will also include the probabilties of their values in the calculation of the
        likelihood
    window_len: int
        length of sliding window for likelihood calculations
    use_start_end_tokens: bool
        if True, then `start_token` and `end_token` will be prepended and appended to the
        session respectively before the calculations are done
    start_token: str
        dummy command to signify the start of the session (e.g. "##START##")
    end_token: str
        dummy command to signify the end of the session (e.g. "##END##")
    use_geo_mean: bool
        if True, then each of the likelihoods of the sliding windows will be raised to the power of
        (1/`window_len`)

    Returns
    -------
    list of likelihoods
    """
    if use_start_end_tokens:
        assert start_token is not None and end_token is not None

    likelihoods = []
    sess = session.copy()
    if use_start_end_tokens:
        sess += [Cmd(name=end_token, params=dict())]
    end = len(sess) - window_len
    for i in range(end + 1):
        window = sess[i : i + window_len]
        if i == 0:
            use_start = use_start_end_tokens
        else:
            use_start = False
        lik = compute_likelihood_window(
            window=window,
            prior_probs=prior_probs,
            trans_probs=trans_probs,
            param_cond_cmd_probs=param_cond_cmd_probs,
            value_cond_param_probs=value_cond_param_probs,
            modellable_params=modellable_params,
            use_start_token=use_start,
            use_end_token=False,
            start_token=start_token,
            end_token=end_token,
        )
        if use_geo_mean:
            k = window_len
            lik = lik ** (1 / k)
        likelihoods.append(lik)

    return likelihoods


def rarest_window_session(
    session: List[Cmd],
    prior_probs: Union[StateMatrix, dict],
    trans_probs: Union[StateMatrix, dict],
    param_cond_cmd_probs: Union[StateMatrix, dict],
    value_cond_param_probs: Union[StateMatrix, dict],
    modellable_params: set,
    window_len: int,
    use_start_end_tokens: bool,
    start_token: str,
    end_token: str,
    use_geo_mean: bool = False,
) -> Tuple[List[Cmd], float]:
    """
    finds and computes the likelihood of the rarest window of length `window_len` from the `session`

    Parameters
    ----------
    session: List[Cmd]
        list of Cmd datatype
        an example session:
            [Cmd(name='Set-User', params={'Identity': 'blahblah', 'Force': 'true'}), Cmd(name='Set-Mailbox',
            params={'Identity': 'blahblah', 'AuditEnabled': 'false'})]
    prior_probs: Union[StateMatrix, dict]
        computed probabilities of individual commands
    trans_probs: Union[StateMatrix, dict]
        computed probabilities of sequences of commands (length 2)
    param_cond_cmd_probs: Union[StateMatrix, dict]
        computed probabilities of the params conditional on the commands
    value_cond_param_probs: Union[StateMatrix, dict]
        computed probabilities of the values conditional on the params
    modellable_params: set
        set of params for which we will also include the probabilties of their values in the calculation of the
        likelihood
    window_len: int
        length of sliding window for likelihood calculations
    use_start_end_tokens: bool
        if True, then `start_token` and `end_token` will be prepended and appended to the
        session respectively before the calculations are done
    start_token: str
        dummy command to signify the start of the session (e.g. "##START##")
    end_token: str
        dummy command to signify the end of the session (e.g. "##END##")
    use_geo_mean: bool
        if True, then each of the likelihoods of the sliding windows will be raised to the power of
        (1/`window_len`)

    Returns
    -------
    Tuple:
        rarest window part of the session,
        likelihood of the rarest window
    """
    likelihoods = compute_likelihood_windows_in_session(
        session=session,
        prior_probs=prior_probs,
        trans_probs=trans_probs,
        param_cond_cmd_probs=param_cond_cmd_probs,
        value_cond_param_probs=value_cond_param_probs,
        modellable_params=modellable_params,
        window_len=window_len,
        use_start_end_tokens=use_start_end_tokens,
        start_token=start_token,
        end_token=end_token,
        use_geo_mean=use_geo_mean,
    )
    if len(likelihoods) == 0:
        return [], np.nan
    min_lik = min(likelihoods)
    ind = likelihoods.index(min_lik)
    return session[ind : ind + window_len], min_lik
