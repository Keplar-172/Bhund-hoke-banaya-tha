import json, glob
for f in sorted(glob.glob('data/scorecards/*.json')):
    with open(f) as fh:
        sc = json.load(fh)
    for inn in sc.get('scorecard', []):
        for bat in inn.get('batsman', []):
            name = bat['name'].lower()
            if 'vaibhav' in name or 'suryavanshi' in name or 'soorya' in name:
                print(f"{f}: {bat['name']} id={bat['id']}")
            if 'arshad' in name:
                print(f"{f}: {bat['name']} id={bat['id']}")
            if 'tejasvi' in name:
                print(f"{f}: {bat['name']} id={bat['id']}")
        for bw in inn.get('bowler', []):
            name = bw['name'].lower()
            if 'vaibhav' in name or 'suryavanshi' in name or 'soorya' in name:
                print(f"{f}: {bw['name']} id={bw['id']}")
            if 'arshad' in name:
                print(f"{f}: {bw['name']} id={bw['id']}")
            if 'tejasvi' in name:
                print(f"{f}: {bw['name']} id={bw['id']}")
