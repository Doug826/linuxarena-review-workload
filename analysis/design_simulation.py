"""Model-based design study for randomized ties. See METHODS.md for estimands and limits."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.polynomial.hermite import hermgauss
from scipy.optimize import brentq, minimize
from scipy.special import betaln, expit, logit, logsumexp
from scipy.stats import binom

ROOT = Path(__file__).resolve().parents[1]
TAB = ROOT / "tables"
SEED = 20261121
X, W = hermgauss(19)
Z, W = X * np.sqrt(2), W / np.sqrt(np.pi)
METHODS = ("pooled", "local", "hierarchical")


def grid(par):
    mu, sd, concentration = par
    means = np.clip(expit(mu + sd * Z), 1e-8, 1 - 1e-8)
    return means, means * concentration, (1 - means) * concentration


def fit(groups_n, groups_k):
    n = np.stack(groups_n)
    k = np.stack(groups_k)
    def nll(v):
        _, a, b = grid((v[0], v[1], np.exp(v[2])))
        log_kernel = betaln(k[...,None]+a, (n-k)[...,None]+b) - betaln(a,b)
        return -logsumexp(np.log(W)+log_kernel.sum(axis=1), axis=1).sum()
    start = logit(np.clip(k.sum()/n.sum(), .0001,.9999))
    fits = [minimize(nll,[start,sd,np.log(12)],method="L-BFGS-B",
                     bounds=[(-12,8),(0,2.8),(np.log(.12),np.log(3e4))])
            for sd in (.15,.85)]
    v = min((r for r in fits if r.success),key=lambda r:r.fun).x
    return np.array([v[0],v[1],np.exp(v[2])])


def update(par, n, k):
    _, a, b = grid(par)
    log_l = (betaln(k[...,None]+a,(n-k)[...,None]+b)-betaln(a,b)).sum(axis=-2)
    log_l += np.log(W)
    return np.exp(log_l-logsumexp(log_l,axis=-1,keepdims=True))


def cut(strict, tied):
    # Flag all affordable ties; if no ties were observed, use the endpoint compatible with the strict rate.
    return np.where(tied>0,np.clip((.01-strict)/np.maximum(tied,1e-15),0,1), (strict<=.01).astype(float))


def policies(pars, n, tail, hi):
    gm, *_ = grid(pars[0])
    gs, *_ = grid(pars[1])
    weights=[update(pars[0],n,tail),update(pars[1],tail,hi)]
    a,b=weights[0]@gm,weights[1]@gs
    pool_a,pool_b=W@gm,W@gs
    q0=float(cut(np.array(pool_a*pool_b),np.array(pool_a*(1-pool_b))))
    denom=n.sum(-1)
    loc=cut(hi.sum(-1)/denom,(tail-hi).sum(-1)/denom)
    return np.stack([np.full_like(loc,q0),loc,cut(a*b,a*(1-b))],axis=-1),weights


def simulate_counts(rng, n, p, phi):
    # One shared latent probability for all steps within each task.
    p=np.broadcast_to(p, np.shape(n))
    pt=rng.beta(np.maximum(1e-8,p*phi),np.maximum(1e-8,(1-p)*phi))
    return rng.binomial(n,pt)


def exact_sign(diff):
    # One-sided sign test, ties omitted, independent target environments within each synthetic study.
    d=diff.reshape(-1,10)
    wins=(d>1e-10).sum(-1)
    non=(np.abs(d)>1e-10).sum(-1)
    return (binom.sf(wins-1,non,.5)<.05).mean()


def mean_signflip(diff):
    # Sensitivity check for the mean, assuming symmetric paired differences under the null.
    d=diff.reshape(-1,10)
    signs=1-2*((np.arange(1024)[:,None] >> np.arange(10)) & 1)
    sims=d@signs.T
    p=(sims>=d.sum(-1)[:,None]-1e-10).mean(-1)
    return (p<.05).mean()


def simulate(df, pars, runs=500):
    rng=np.random.default_rng(SEED)
    summaries=[]
    nenv=runs*10
    for scenario in ["no_environment_effect","fitted","stronger_shift"]:
        gen=np.array(pars).copy()
        if scenario=="no_environment_effect":
            gen[:,1]=0
        if scenario=="stronger_shift":
            gen[:,1]=np.maximum(2*gen[:,1], [.7,.35])
        # Keep the marginal tail prevalence comparable when changing environment spread.
        for j in range(2):
            marginal=W@grid(pars[j])[0]
            gen[j,0]=brentq(lambda mu: W@expit(mu+gen[j,1]*Z)-marginal,-30,30)
        # The method has the true source population parameters: optimistic about learning the prior.
        p=[expit(v[0]+v[1]*rng.normal(size=(nenv,1))) for v in gen]
        n=rng.choice(df.n.to_numpy(),size=(nenv,260))
        tail=simulate_counts(rng,n,p[0],gen[0,2])
        hi=simulate_counts(rng,tail,p[1],gen[1,2])
        for m,t in [(1,10),(2,10),(5,15),(10,10),(20,10),(40,10),(80,10),(160,10),(10,100)]:
            q,_=policies(gen,n[:,:m],tail[:,:m],hi[:,:m])
            # For the larger training designs keep a 10-task evaluation set, as in the 10-task design.
            ns=n[:,-t:].sum(-1); hs=hi[:,-t:].sum(-1); tied=(tail[:,-t:]-hi[:,-t:]).sum(-1)
            # Paired methods see the same tasks and tie lottery. Binomial draws over nested tie fractions.
            order=np.argsort(q,axis=1); sq=np.take_along_axis(q,order,axis=1)
            remaining=tied.copy(); prev=np.zeros(nenv); hits=np.zeros(nenv,dtype=int)
            alerts=np.empty((nenv,3),int)
            for i in range(3):
                prob=np.clip((sq[:,i]-prev)/np.maximum(1-prev,1e-15),0,1)
                inc=rng.binomial(remaining,prob);remaining-=inc;hits+=inc
                alerts[np.arange(nenv),order[:,i]]=hs+hits
                prev=sq[:,i]
            obs=abs(1000*alerts/ns[:,None]-10)
            expected=abs(1000*p[0]*(p[1]+q*(1-p[1]))-10)
            for i,method in enumerate(METHODS):
                rec=dict(scenario=scenario,calibration_tasks=m,test_tasks=t,method=method,
                         true_budget_mae=expected[:,i].mean(),test_budget_mae=obs[:,i].mean(),
                         studies=runs,prob_detect_better_than_pooled=None,
                         prob_detect_worse_than_pooled=None,prob_detect_better_than_local=None,
                         prob_detect_mean_better_than_pooled=None)
                if i!=0:
                    rec["prob_detect_better_than_pooled"]=exact_sign(obs[:,0]-obs[:,i])
                    rec["prob_detect_mean_better_than_pooled"]=mean_signflip(obs[:,0]-obs[:,i])
                    rec["prob_detect_worse_than_pooled"]=exact_sign(obs[:,i]-obs[:,0])
                if i==2:
                    rec["prob_detect_better_than_local"]=exact_sign(obs[:,1]-obs[:,2])
                summaries.append(rec)
    return pd.DataFrame(summaries)


def draw_mean(rng,par,prob,reps):
    mean=grid(par)[0]
    return mean[rng.choice(len(mean),reps,p=prob)][:,None]


def predictive_scores(df,reps=400,partitions=16):
    """Check 80% workload intervals on disjoint local calibration/test tasks. Repeated partitions overlap."""
    rng=np.random.default_rng(SEED+1)
    out=[]
    for env in sorted(df.environment.unique()):
        local=df[df.environment==env]
        src=df[df.environment!=env]
        pars=fit_both(src)
        for repeat in range(partitions):
            idx=rng.permutation(len(local))
            for m in (5,10):
                tr=local.iloc[idx[:m]]
                te=local.iloc[idx[m:]]
                n=tr.n.to_numpy(); u=(tr.strict+tr.tie).to_numpy(); h=tr.strict.to_numpy()
                q,w=policies(pars,n[None],u[None],h[None])
                # Realized audit lottery shared across methods on measured test ties.
                uniforms=rng.random(te.tie.sum())
                for j,method in enumerate(METHODS):
                    observed=te.strict.sum()+(uniforms<q[0,j]).sum()
                    if method=="local":
                        # Plug-in forecast. Gives local-only learning a common source estimate of task dispersion.
                        mu=[np.full((reps,1),(u.sum()+.5)/(n.sum()+1)),
                            np.full((reps,1),(h.sum()+.5)/(u.sum()+1))]
                    else:
                        ww=[W,W] if method=="pooled" else [w[0][0],w[1][0]]
                        mu=[draw_mean(rng,v,pr,reps) for v,pr in zip(pars,ww)]
                    nn=np.broadcast_to(te.n.to_numpy(),(reps,len(te)))
                    tt=simulate_counts(rng,nn,np.broadcast_to(mu[0],nn.shape),pars[0][2])
                    hh=simulate_counts(rng,tt,np.broadcast_to(mu[1],nn.shape),pars[1][2])
                    draw=(hh+rng.binomial(tt-hh,q[0,j])).sum(-1)
                    lo,hi=np.quantile(draw,[.1,.9],method="inverted_cdf")
                    score=hi-lo+10*(max(lo-observed,0)+max(observed-hi,0))
                    out.append(dict(environment=env,repeat=repeat,calibration_tasks=m,method=method,
                                    covered=int(lo<=observed<=hi),width=hi-lo,interval_score=score))
    return pd.DataFrame(out)


def fit_both(df):
    groups=[g for _,g in df.groupby("environment",sort=True)]
    n=[g.n.to_numpy() for g in groups]; tail=[(g.strict+g.tie).to_numpy() for g in groups]
    return np.array([fit(n,tail),fit(tail,[g.strict.to_numpy() for g in groups])])


def main():
    df=pd.read_csv(TAB/"honest_tasks.csv")
    pars=fit_both(df)
    meta={k:dict(logit_center=v[0],environment_logit_sd=v[1],task_concentration=v[2])
          for k,v in zip(["at_or_above_7p5","strict_given_at_or_above_7p5"],pars)}
    (TAB/"simulation_fit.json").write_text(json.dumps(meta,indent=2)+"\n")
    simulate(df,pars).to_csv(TAB/"simulation.csv",index=False)
    raw=predictive_scores(df)
    raw.to_csv(TAB/"predictive_splits.csv",index=False)
    raw.groupby(["calibration_tasks","method"])[["covered","width","interval_score"]].mean().to_csv(TAB/"predictive_summary.csv")
    print(meta)


if __name__=="__main__":
    main()
