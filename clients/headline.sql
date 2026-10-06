-- The four headline numbers off a directory of archives, for every scenario at
-- once, in a DuckDB shell with nothing installed. The globs are relative, so
-- this runs from the repository root, and `runs/` is written by the solve job
-- rather than checked in:
--
--     uv run showcase-solve --runs runs     # once, if runs/ is not there yet
--     duckdb -c ".read clients/headline.sql"
--
-- The first statement is why a wrong directory or a missing archive says which
-- of those two to run, rather than reporting a path that does not exist.
--
-- Every file carries `specsolve_run`, the archive's directory name, so the
-- globs concatenate across archives as they stand. The record names its period
-- in `slice`, as text. Point the globs at another directory and the query is
-- unchanged.
select error('no archive under runs/ — run `uv run showcase-solve --runs runs` first, from the repository root')
from (select 1) where (select count(*) from glob('runs/*/answer/record.parquet')) = 0;

with objective as (
    select specsolve_run as run, slice::integer as year, objective
    from read_parquet('runs/*/answer/record.parquet', union_by_name = true)
),
period as (select run, min(year) as first, max(year) as last from objective group by run),
value_of as (
    select specsolve_run as run, 'emissions' as quantity, year, null as generator, value
        from read_parquet('runs/*/answer/expression/emissions.parquet')
    union all by name
    select specsolve_run as run, 'carbon' as quantity, year, null as generator, value
        from read_parquet('runs/*/answer/dual/carbon.parquet')
    union all by name
    select specsolve_run as run, 'total' as quantity, year, generator, value
        from read_parquet('runs/*/answer/primal/total.parquet')
),
clean as (
    select specsolve_run as run, generator
    from read_parquet('runs/*/sources/rate.parquet')
    where value = 0
)
select
    p.run,
    (select sum(objective) from objective o where o.run = p.run) as pathway_cost,
    1 - (select sum(value) from value_of v where v.run = p.run and v.quantity = 'emissions' and v.year = p.last)
      / (select sum(value) from value_of v where v.run = p.run and v.quantity = 'emissions' and v.year = p.first) as emissions_cut,
    (select sum(value) from value_of v join clean c on c.run = v.run and c.generator = v.generator
        where v.run = p.run and v.quantity = 'total' and v.year = p.last)
      / (select sum(value) from value_of v where v.run = p.run and v.quantity = 'total' and v.year = p.last) as zero_carbon_share,
    -coalesce((select sum(value) from value_of v where v.run = p.run and v.quantity = 'carbon' and v.year = p.last), 0) + 0.0 as carbon_price
from period p
order by p.run;
