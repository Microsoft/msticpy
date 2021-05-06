# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Pivot pipeline class."""
from collections import namedtuple
from typing import Any, Dict, Iterable, List, Optional

import attr
import pandas as pd
import yaml
from attr import Factory
from tqdm.auto import tqdm

from .._version import VERSION
from . import entities

__version__ = VERSION
__author__ = "Ian Hellen"


_STEP_TYPES = {
    "pivot": "mp_pivot.run",
    "pivot_display": "mp_pivot.display",
    "pivot_tee": "mp_pivot.tee",
    "pivot_tee_exec": "mp_pivot.tee_exec",
    "pd_accessor": None,
}

PipelineExecStep = namedtuple(
    "PipelineExecStep", "accessor, pos_params, params, text, comment"
)


@attr.s(auto_attribs=True)
class PipelineStep:
    """Pivot pipeline step class."""

    name: str
    step_type: str = attr.ib(validator=attr.validators.in_(_STEP_TYPES))
    function: Optional[str] = None
    entity: Optional[str] = None
    comment: Optional[str] = None
    pos_params: List[str] = Factory(list)
    params: Dict[str, Any] = Factory(dict)

    def get_exec_step(self) -> PipelineExecStep:
        """
        Return the executable step details.

        Returns
        -------
        PipelineExecStep
            Named tuple with the following fields
            accessor - the name of the pandas DataFrame accessor function
            params - parameters to be passed to the function
            text - the text representation of the accessor + params
            comment - optional comment that can be used by the pipeline
            builder to add Python comments to output.

        """
        if self.step_type not in _STEP_TYPES:
            raise TypeError(f"Invalid step type {self.step_type}")

        mp_func = _STEP_TYPES[self.step_type]
        accessor = mp_func
        params = self.params
        func_text = f".{mp_func}({self._get_param_string()})"

        if self.step_type == "pivot":
            _, func = _get_entity_and_pivot(self.entity, self.function)
            func_text = (
                f".{mp_func}({self.entity}.{self.function}, {self._get_param_string()})"
            )
            params = {"func": func, **(self.params)}
        elif self.step_type == "pivot_tee_exec":
            func_text = f".{mp_func}('{self.function}', {self._get_param_string()})"
            params = {"df_func": self.function, **(self.params)}
        elif self.step_type == "pd_accessor":
            func_text = f".{self.function}({self._get_param_string()})"
            accessor = self.function

        return PipelineExecStep(
            accessor=accessor,
            pos_params=self.pos_params,
            params=params,
            text=func_text,
            comment=self.comment,
        )

    # pylint: disable=no-member, not-an-iterable
    def _get_param_string(self) -> str:
        """Return text representation of keyword params."""
        pos_params = [
            f"'{param}'" if isinstance(param, str) else str(param)
            for param in self.pos_params
        ]
        params_str = [
            f"{p_name}='{p_val}'"
            for p_name, p_val in self.params.items()
            if isinstance(p_val, str)
        ]
        params_other = [
            f"{p_name}={p_val}"
            for p_name, p_val in self.params.items()
            if not isinstance(p_val, str)
        ]
        return ", ".join(pos_params + params_str + params_other)

    # pylint: enable=no-member, not-an-iterable


def _get_entity_and_pivot(entity_name, func_name):
    """Return the entity and pivot function as objects."""
    entity = getattr(entities, entity_name)
    func_name_path = func_name.split(".")
    obj = entity
    for path in func_name_path:
        obj = getattr(obj, path)
    return entity, obj


def _get_pd_accessor_func(data, df_func):
    """Return the function accessor `df_func` for the DataFrame `df`."""
    acc_name = func_name = func = None
    if "." in df_func:
        acc_name, func_name = df_func.split(".")
        accessor = getattr(data, acc_name, None)
        if accessor:
            func = getattr(accessor, func_name, None)
    else:
        func = getattr(data, df_func, None)
    if func:
        # run the function with any additional args
        return func
    return None


class Pipeline:
    """Pivot pipeline."""

    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        steps: Optional[Iterable[PipelineStep]] = None,
    ):
        """
        Create Pipeline instance.

        Parameters
        ----------
        name : str
            The pipeline name.
        description : Optional[str]
            The pipeline description, by default None.
        steps : Optional[Iterable[PipelineStep]]
            Pipeline steps, by default None.

        """
        self.name = name
        self.description = description
        self.steps: List[PipelineStep] = []
        if steps:
            for step in steps:
                self.steps.append(step)

    def __repr__(self) -> str:
        """
        Return string representation of pipeline.

        Returns
        -------
        str
            string representation of pipeline

        """
        step_repr = "\n  ".join(str(step) for step in self.steps)
        return (
            f"Pipeline(name='{self.name}', description='{self.description}', "
            + f"steps=[{step_repr}])"
        )

    @classmethod
    def parse_pipeline(cls, pipeline: Dict[str, Dict[str, Any]]) -> "Pipeline":
        """
        Parse single pipeline from dictionary.

        Parameters
        ----------
        pipeline : Dict[str, Dict[str, Any]]
            Single pipeline as a dictionary:
            {name: {pipeline_dict...}}.

        Returns
        -------
        Pipeline
            The pivot pipeline.

        Raises
        ------
        ValueError
            The dictionary could not be parsed as a pipeline.

        """
        pl_name, pl_dict = next(iter(pipeline.items()))
        if pl_dict and isinstance(pl_dict, dict):
            steps = [PipelineStep(**step) for step in pl_dict.get("steps", [])]
            return cls(
                name=pl_name, description=pl_dict.get("description"), steps=steps
            )
        raise ValueError("Dictionary could not be parsed.")

    @staticmethod
    def parse_pipelines(pipelines: Dict[str, Dict[str, Any]]) -> Iterable["Pipeline"]:
        """
        Parse dict of pipelines.

        Parameters
        ----------
        pipelines : Dict[str, Dict[str, Any]]
            Dict of pipelines.

        Yields
        ------
        Pipeline
            Iterable of pipeline instances

        """
        for p_name, pipeline in pipelines.get("pipelines", {}).items():
            yield Pipeline.parse_pipeline({p_name: pipeline})

    @classmethod
    def from_yaml(cls, yml_str: str) -> Iterable["Pipeline"]:
        """
        Parse pipelines from yaml string.

        Parameters
        ----------
        yml_str : str
            Yaml dict of pipelines.

        Yields
        ------
        Pipeline
            Iterable of pipeline instances

        """
        pipelines = yaml.safe_load(yml_str)
        yield from cls.parse_pipelines(pipelines)

    def to_yaml(self) -> str:
        """
        Return yaml representation of pipeline.

        Returns
        -------
        str
            Pipeline as yaml.

        """
        steps = [attr.asdict(step) for step in self.steps]
        return yaml.dump({self.name: {"description": self.description, "steps": steps}})

    def run(
        self, data: pd.DataFrame, verbose: bool = True, debug: bool = False
    ) -> Optional[Any]:
        """
        Run the pipeline on the supplied DataFrame.

        Parameters
        ----------
        data : pd.DataFrame
            Input DataFrame for pipeline
        verbose : bool, optional
            If True, report progress, by default True
        debug : bool, optional
            If True, report more detailed progress, by default False

        Returns
        -------
        Any
            The output of the last stage of the pipeline

        """
        pipeline_result = data
        pipe_linesteps = tqdm(self.steps, desc="Steps") if verbose else self.steps
        for step in pipe_linesteps:
            exec_action = step.get_exec_step()
            if verbose:
                print("step =", step.name, "\n", exec_action)
            if not isinstance(pipeline_result, pd.DataFrame):
                print(
                    "Output type from previous step is {type(pipeline_result}",
                    "This is not a valid input type for the next stage.",
                )
                break
            exec_kws = {"verbose": verbose, "debug": debug}
            func = _get_pd_accessor_func(pipeline_result, exec_action.accessor)
            pipeline_result = func(
                *exec_action.pos_params, **exec_action.params, **exec_kws
            )

        return pipeline_result

    def print_pipeline(self, df_name: str = "input_df", comments: bool = True) -> str:
        """
        Return the pipeline as text that can be executed in Python.

        Parameters
        ----------
        df_name : str, optional
            Name of the input dataframe to be used in the returned
            code, by default "input_df"
        comments : bool, optional
            If True show step comments, by default True

        Returns
        -------
        str
            The executable pipeline text.

        """
        step_list = []
        if comments:
            step_list.append(f"# {self.description or self.name}")
        step_list.extend(["(", f"    {df_name}"])
        for step in self.steps:
            exec_action = step.get_exec_step()
            if comments:
                step_list.append(f"    # {step.comment or step.name}")
            step_list.append(f"    {exec_action.text}")
        step_list.append(")")
        return "\n".join(step_list)
