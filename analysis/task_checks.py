"""Offline checks from blinded task-level counts. No raw benchmark files or network required."""
import json
import random
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import xlogy
from scipy.stats import chi2_contingency

ROOT=Path(__file__).resolve().parents[1]
TAB=ROOT/"tables"


def predict_mix(df):
    """Held-out mean count prediction, task length as exposure; fixed shrinkage of 10 source tasks per group."""
    results=[]
    for env in sorted(df.environment.unique()):
        train=df.loc[df.environment!=env]
        test=df.loc[df.environment==env].copy()
        base=train.strict.sum()/train.n.sum()
        prior_n=10*train.n.mean()
        for attr in ("pooled","category","topic_any","category_and_topic"):
            group_rates={}
            if attr!="pooled":
                for group,g in train.groupby(attr):
                    group_rates[group]=(g.strict.sum()+prior_n*base)/(g.n.sum()+prior_n)
            rates=test[attr].map(group_rates).fillna(base) if attr!="pooled" else base
            pred=test.n*rates
            loss=2*(xlogy(test.strict,test.strict/pred)-(test.strict-pred))
            results.append(dict(environment=env,predictor=attr,poisson_deviance_per_task=loss.mean()))
    return pd.DataFrame(results)


def main():
    df=pd.read_csv(TAB/"honest_tasks.csv")
    assert len(df)==200 and df.code.nunique()==200 and (df.n==df[[f"s{i:02}" for i in range(21)]].sum(axis=1)).all()
    env=df.groupby("environment").agg(n=("n","sum"),alerts=("strict","sum"),ties=("tie","sum"),tasks=("n","size"))
    p=df.strict.sum()/df.n.sum()
    pearson=chi2_contingency(np.column_stack([env.alerts,env.n-env.alerts]),correction=False)
    # Descriptive whole-task sandwich variance for the pooled count / pooled exposure estimator.
    V=len(df)/(len(df)-1)*sum((df.strict-p*df.n)**2)/df.n.sum()**2
    de=V/(p*(1-p)/df.n.sum())
    # Use the exact original stable order (the table rows were exported in environment and task-ID order).
    pairs=list(zip(df.strict,df.n))
    def disp(groups):
        return sum(y*y/n for y,n in groups)
    observed=disp(zip(env.alerts,env.n))
    rng=random.Random(20261119);above=0
    for _ in range(9999):
        rng.shuffle(pairs)
        blocks=[pairs[i:i+20] for i in range(0,200,20)]
        value=disp((sum(y for y,n in b),sum(n for y,n in b)) for b in blocks)
        above+=(value>=observed-1e-12)
    df["topic_any"]=df[["access","credential","network"]].max(axis=1)
    df["category_and_topic"]=df.category+"_"+df.topic_any.astype(str)
    def tab(g):
        return {"tasks":len(g),"n_actions":int(g.n.sum()),"alerts":int(g.strict.sum()),
                "tasks_flagged":int((g.strict>0).sum()),"per_1000":1000*g.strict.sum()/g.n.sum()}
    descriptive=[dict(grouping="category",group=k,**tab(g)) for k,g in df.groupby("category")]
    for attr in ("access","credential","network","topic_any"):
        for k,g in df.groupby(attr):
            descriptive.append(dict(grouping=attr,group=str(k),**tab(g)))
    pd.DataFrame(descriptive).to_csv(TAB/"task_mix.csv",index=False)
    scores=predict_mix(df);scores.to_csv(TAB/"task_mix_predictions.csv",index=False)
    summary=dict(independent_action_pearson=float(pearson.statistic),independent_action_p=float(pearson.pvalue),
                 omnibus_task_permutation_p=(above+1)/10000,design_effect_pooled_rate=de,
                 approximate_alert_equivalent_pooled_rate=df.strict.sum()/de,
                 n_tasks_with_alerts=int((df.strict>0).sum()),independent_expected_tasks_with_alerts=float((1-(1-p)**df.n).sum()),
                 top_10_tasks_alerts=int(df.strict.nlargest(10).sum()),task_mix_heldout_deviance=scores.groupby("predictor").poisson_deviance_per_task.mean().to_dict())
    (TAB/"task_checks.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary,indent=2))
    print(pd.DataFrame(descriptive).to_string(index=False))


if __name__=="__main__":
    main()
