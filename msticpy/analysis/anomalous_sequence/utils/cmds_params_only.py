from collections import defaultdict
import numpy as np
from typing import Tuple, List, Union

from msticpy.analysis.anomalous_sequence.utils.data_structures import StateMatrix, Cmd


def compute_counts(sessions: List[List[Cmd]], start_token: str = '##START##', end_token: str = '##END##',
                   unk_token: str = '##UNK##') -> Tuple[StateMatrix, StateMatrix, StateMatrix, StateMatrix]:
    """
    computes counts of individual commands and of sequences of two commands. It also computes the counts of
    individual params as well as counts of params conditional on the command

    Laplace smoothing is applied to the counts.
    This is so we shift some of the probability mass from the very probable commands/params to the unseen and very
    unlikely commands/params.
    The `unk_token` means we can handle unseen commands, sequences of commands and params

    Parameters
    ----------
    sessions: List[List[Cmd]]
        each session is a list of the Cmd datatype. Where the Cmd datatype has a name attribute (command name) and a
        params attribute (set containing params associated with the command)
        an example session:
            [Cmd(name='Set-User', params={'Identity', 'Force'}), Cmd(name='Set-Mailbox', params={'Identity',
            'AuditEnabled'})]
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

    """

    seq1_counts = defaultdict(lambda: 0)
    seq2_counts = defaultdict(lambda: defaultdict(lambda: 0))

    param_counts = defaultdict(lambda: 0)
    cmd_param_counts = defaultdict(lambda: defaultdict(lambda: 0))

    for session in sessions:
        prev = start_token
        seq1_counts[prev] += 1
        for cmd in session:
            seq1_counts[cmd.name] += 1
            seq2_counts[prev][cmd.name] += 1
            prev = cmd.name
            for p in cmd.params:
                param_counts[p] += 1
                cmd_param_counts[cmd.name][p] += 1
        seq2_counts[prev][end_token] += 1
        seq1_counts[end_token] += 1

    # apply laplace smoothing for cmds
    cmds = list(seq1_counts.keys()) + [unk_token]
    for cmd1 in cmds:
        for cmd2 in cmds:
            if cmd1 != end_token and cmd2 != start_token:
                seq1_counts[cmd1] += 1
                seq2_counts[cmd1][cmd2] += 1
                seq1_counts[cmd2] += 1

    # apply laplace smoothing for params
    params = list(param_counts.keys()) + [unk_token]
    for cmd in cmds:
        for param in params:
            if param in cmd_param_counts[cmd] or param == unk_token:
                param_counts[param] += 1
                cmd_param_counts[cmd][param] += 1

    seq1_counts = StateMatrix(states=seq1_counts, unk_token=unk_token)
    seq2_counts = StateMatrix(states=seq2_counts, unk_token=unk_token)
    param_counts = StateMatrix(states=param_counts, unk_token=unk_token)
    cmd_param_counts = StateMatrix(states=cmd_param_counts, unk_token=unk_token)

    return seq1_counts, seq2_counts, param_counts, cmd_param_counts


def compute_prob_setofparams_given_cmd(cmd: str, params: set, param_cond_cmd_probs: Union[StateMatrix, dict],
                                       use_geo_mean: bool = True) -> float:
    """
    Given a command and its accompanying params, compute the probabilty of that set of params appearing,
    conditional on the command

    Parameters
    ----------
    cmd: str
        name of command
        (e.g. for Exchange powershell commands: "Set-Mailbox")
    params: set
        set of accompanying params for the cmd
        (e.g for Exchange powershell commands: {'Identity', 'ForwardingEmailAddress'})
    param_cond_cmd_probs: Union[StateMatrix, dict]
        computed probabilities of params conditional on the command
    use_geo_mean: bool
        if True, then the likelihood will be raised to the power of (1/K) where K is the number of
        distinct params which appeared for the given `cmd` across our training set.
        Note:
        Some commands may have more params set in general compared with other commands. It can be useful to use the
        geo mean so that you can compare this probability across different commands with differing number of params

    Returns
    -------
    computed likelihood
    """
    if len(params) == 0:
        return 1
    ref = param_cond_cmd_probs[cmd]
    prob = 1
    for param, p in ref.items():
        if param in params:
            prob *= p
        else:
            prob *= (1 - p)
    if use_geo_mean:
        k = len(ref)
        prob = prob ** (1 / k)

    return prob


def compute_likelihood_window(window: List[Cmd], prior_probs: Union[StateMatrix, dict],
                              trans_probs: Union[StateMatrix, dict], param_cond_cmd_probs: Union[StateMatrix, dict],
                              use_start_token: bool, use_end_token: bool, start_token: str = None,
                              end_token: str = None) -> float:
    """
    computes the likelihood of the input `window`

    Parameters
    ----------
    window: List[Cmd]
        part or all of a session, where a session is a list of the Cmd datatype
        an example session:
            [Cmd(name='Set-User', params={'Identity', 'Force'}), Cmd(name='Set-Mailbox', params={'Identity',
            'AuditEnabled'})]
    prior_probs: Union[StateMatrix, dict]
        computed probabilities of individual commands
    trans_probs: Union[StateMatrix, dict]
         computed probabilities of sequences of commands (length 2)
    param_cond_cmd_probs: Union[StateMatrix, dict]
        computed probabilities of the params conditional on the commands
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
    param_cond_prob = compute_prob_setofparams_given_cmd(
        cmd=cur_cmd,
        params=params,
        param_cond_cmd_probs=param_cond_cmd_probs,
        use_geo_mean=True)

    if use_start_token:
        prob *= trans_probs[start_token][cur_cmd] * param_cond_prob
    else:
        prob *= prior_probs[cur_cmd] * param_cond_prob

    for i, cmdparam in enumerate(window[1:]):
        prev, cur = window[i - 1], window[i]
        prev_cmd, cur_cmd = prev.name, cur.name
        prev_par, cur_par = prev.params, cur.params
        prob *= trans_probs[prev_cmd][cur_cmd]
        param_cond_prob = compute_prob_setofparams_given_cmd(
            cmd=cur_cmd,
            params=cur_par,
            param_cond_cmd_probs=param_cond_cmd_probs,
            use_geo_mean=True)
        prob *= param_cond_prob

    if use_end_token:
        prob *= trans_probs[cur_cmd][end_token]

    return prob


def compute_likelihood_windows_in_session(session: List[Cmd], prior_probs: Union[StateMatrix, dict],
                                          trans_probs: Union[StateMatrix, dict],
                                          param_cond_cmd_probs: Union[StateMatrix, dict], window_len: int,
                                          use_start_end_tokens: bool, start_token: str = None,
                                          end_token: str = None, use_geo_mean: bool = False) -> List[float]:
    """
    computes the likelihoods of a sliding window of length `window_len` throughout the session

    Parameters
    ----------
    session: List[Cmd]
        list of Cmd datatype
        an example session:
            [Cmd(name='Set-User', params={'Identity', 'Force'}), Cmd(name='Set-Mailbox', params={'Identity',
            'AuditEnabled'})]
    prior_probs: Union[StateMatrix, dict]
        computed probabilities of individual commands
    trans_probs: Union[StateMatrix, dict]
         computed probabilities of sequences of commands (length 2)
    param_cond_cmd_probs: Union[StateMatrix, dict]
        computed probabilities of the params conditional on the command
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
        sess += [Cmd(name=end_token, params={})]
    end = len(sess) - window_len
    for i in range(end + 1):
        window = sess[i: i + window_len]
        if i == 0:
            use_start = use_start_end_tokens
        else:
            use_start = False
        lik = compute_likelihood_window(
            window=window,
            prior_probs=prior_probs,
            trans_probs=trans_probs,
            param_cond_cmd_probs=param_cond_cmd_probs,
            use_start_token=use_start,
            use_end_token=False,
            start_token=start_token,
            end_token=end_token
        )
        if use_geo_mean:
            k = window_len
            lik = lik ** (1 / k)
        likelihoods.append(lik)

    return likelihoods


def rarest_window_session(session: List[Cmd], prior_probs: StateMatrix, trans_probs: StateMatrix,
                          param_cond_cmd_probs: StateMatrix, window_len: int,
                          use_start_end_tokens: bool, start_token: str, end_token: str,
                          use_geo_mean=False) -> Tuple[List[Cmd], float]:
    """
    finds and computes the likelihood of the rarest window of length `window_len` from the `session`

    Parameters
    ----------
    session: List[Cmd]
        list of Cmd datatype
        an example session:
            [Cmd(name='Set-User', params={'Identity', 'Force'}), Cmd(name='Set-Mailbox', params={'Identity',
            'AuditEnabled'})]
    prior_probs: Union[StateMatrix, dict]
        computed probabilities of individual commands
    trans_probs: Union[StateMatrix, dict]
         computed probabilities of sequences of commands (length 2)
    param_cond_cmd_probs: Union[StateMatrix, dict]
        computed probabilities of the params conditional on the command
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
        window_len=window_len,
        use_start_end_tokens=use_start_end_tokens,
        start_token=start_token,
        end_token=end_token,
        use_geo_mean=use_geo_mean
    )
    if len(likelihoods) == 0:
        return [], np.nan
    min_lik = min(likelihoods)
    ind = likelihoods.index(min_lik)
    return session[ind:ind + window_len], min_lik
