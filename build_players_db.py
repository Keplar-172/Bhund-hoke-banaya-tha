"""One-time script to build players_data.json from teams_data.json + IPL squad data."""
import json
import re
from collections import Counter

# IPL Squad data from iplt20.com
IPL_SQUADS = {
    "CSK": [
        "Ruturaj Gaikwad", "MS Dhoni", "Sanju Samson", "Dewald Brevis", "Ayush Mhatre",
        "Kartik Sharma", "Sarfaraz Khan", "Urvil Patel",
        "Jamie Overton", "Ramakrishna Ghosh", "Prashant Veer", "Matthew William Short",
        "Aman Khan", "Zak Foulkes", "Shivam Dube",
        "Khaleel Ahmed", "Noor Ahmad", "Anshul Kamboj", "Mukesh Choudhary",
        "Shreyas Gopal", "Gurjapneet Singh", "Akeal Hosein", "Matt Henry",
        "Rahul Chahar", "Spencer Johnson"
    ],
    "DC": [
        "KL Rahul", "Karun Nair", "David Miller", "Ben Duckett", "Pathum Nissanka",
        "Sahil Parakh", "Prithvi Shaw", "Abishek Porel", "Tristan Stubbs",
        "Axar Patel", "Sameer Rizvi", "Ashutosh Sharma", "Vipraj Nigam",
        "Ajay Mandal", "Tripurana Vijay", "Madhav Tiwari", "Nitish Rana",
        "Mitchell Starc", "T Natarajan", "Mukesh Kumar", "Dushmantha Chameera",
        "Auqib Nabi", "Lungisani Ngidi", "Kyle Jamieson", "Kuldeep Yadav"
    ],
    "KKR": [
        "Ajinkya Rahane", "Rinku Singh", "Angkrish Raghuvanshi", "Manish Pandey",
        "Finn Allen", "Tejasvi Singh", "Rahul Tripathi", "Tim Seifert", "Rovman Powell",
        "Anukul Roy", "Cameron Green", "Sarthak Ranjan", "Daksh Kamra",
        "Rachin Ravindra", "Ramandeep Singh", "Sunil Narine",
        "Blessing Muzarabani", "Vaibhav Arora", "Matheesha Pathirana",
        "Kartik Tyagi", "Prashant Solanki", "Saurabh Dubey", "Navdeep Saini",
        "Umran Malik", "Varun Chakaravarthy"
    ],
    "RR": [
        "Shubham Dubey", "Vaibhav Suryavanshi", "Donovan Ferreira",
        "Lhuan-dre Pretorious", "Ravi Singh", "Aman Rao Perala",
        "Shimron Hetmyer", "Yashasvi Jaiswal", "Dhruv Jurel",
        "Riyan Parag", "Yudhvir Singh Charak", "Ravindra Jadeja", "Dasun Shanaka",
        "Jofra Archer", "Tushar Deshpande", "Kwena Maphaka", "Ravi Bishnoi",
        "Sushant Mishra", "Yash Raj Punja", "Vignesh Puthur", "Brijesh Sharma",
        "Adam Milne", "Kuldeep Sen", "Sandeep Sharma", "Nandre Burger"
    ],
    "SRH": [
        "Ishan Kishan", "Aniket Verma", "Smaran Ravichandran", "Salil Arora",
        "Heinrich Klaasen", "Travis Head",
        "Harshal Patel", "Kamindu Mendis", "Harsh Dubey", "Dilshan Madushanka",
        "Shivang Kumar", "Krains Fuletra", "Liam Livingstone", "David Payne",
        "Abhishek Sharma", "Nitish Kumar Reddy",
        "Pat Cummins", "Zeeshan Ansari", "Jaydev Unadkat", "Eshan Malinga",
        "Sakib Hussain", "Onkar Tarmale", "Amit Kumar", "Praful Hinge", "Shivam Mavi"
    ],
    "RCB": [
        "Rajat Patidar", "Devdutt Padikkal", "Virat Kohli", "Phil Salt",
        "Jitesh Sharma", "Jordan Cox",
        "Krunal Pandya", "Swapnil Singh", "Tim David", "Romario Shepherd",
        "Jacob Bethell", "Venkatesh Iyer", "Satvik Deswal", "Mangesh Yadav",
        "Vicky Ostwal", "Vihaan Malhotra", "Kanishk Chouhan",
        "Josh Hazlewood", "Rasikh Dar", "Suyash Sharma", "Bhuvneshwar Kumar",
        "Nuwan Thushara", "Abhinandan Singh", "Jacob Duffy", "Yash Dayal"
    ],
    "MI": [
        "Rohit Sharma", "Suryakumar Yadav", "Robin Minz", "Sherfane Rutherford",
        "Ryan Rickelton", "Quinton de Kock", "Danish Malewar", "Tilak Varma",
        "Hardik Pandya", "Naman Dhir", "Mitchell Santner", "Raj Angad Bawa",
        "Atharva Ankolekar", "Mayank Rawat", "Corbin Bosch", "Will Jacks", "Shardul Thakur",
        "Trent Boult", "Mayank Markande", "Deepak Chahar", "Ashwani Kumar",
        "Raghu Sharma", "Mohammad Izhar", "Allah Ghazanfar", "Jasprit Bumrah",
        "Aryan Juyal"
    ],
    "GT": [
        "Shubman Gill", "Jos Buttler", "Kumar Kushagra", "Anuj Rawat",
        "Tom Banton", "Glenn Phillips", "Sai Sudharsan",
        "Nishant Sindhu", "Washington Sundar", "Mohd Arshad Khan", "Sai Kishore",
        "Jayant Yadav", "Jason Holder", "Rahul Tewatia", "Shahrukh Khan",
        "Kagiso Rabada", "Mohammed Siraj", "Prasidh Krishna", "Manav Suthar",
        "Gurnoor Singh Brar", "Ishant Sharma", "Ashok Sharma", "Luke Wood",
        "Kulwant Khejroliya", "Rashid Khan"
    ],
    "LSG": [
        "Rishabh Pant", "Aiden Markram", "Himmat Singh", "Matthew Breetzke",
        "Mukul Choudhary", "Akshat Raghuwanshi", "Josh Inglis", "Nicholas Pooran",
        "Mitchell Marsh", "Abdul Samad", "Shahbaz Ahamad", "Arshin Kulkarni",
        "Wanindu Hasaranga", "Ayush Badoni",
        "Mohammad Shami", "Avesh Khan", "M Siddharth", "Digvesh Singh",
        "Akash Singh", "Prince Yadav", "Arjun Tendulkar", "Anrich Nortje",
        "Naman Tiwari", "Mayank Yadav", "Mohsin Khan"
    ],
    "PBKS": [
        "Shreyas Iyer", "Nehal Wadhera", "Vishnu Vinod", "Harnoor Pannu",
        "Pyla Avinash", "Prabhsimran Singh", "Shashank Singh",
        "Marcus Stoinis", "Harpreet Brar", "Marco Jansen", "Azmatullah Omarzai",
        "Priyansh Arya", "Musheer Khan", "Suryansh Shedge", "Mitchell Owen",
        "Cooper Connolly", "Ben Dwarshuis",
        "Arshdeep Singh", "Yuzvendra Chahal", "Vyshak Vijaykumar", "Yash Thakur",
        "Xavier Bartlett", "Pravin Dubey", "Vishal Nishad", "Lockie Ferguson"
    ]
}


def normalize(name):
    """Strip dots, hyphens, extra spaces; lowercase."""
    n = name.lower().strip()
    n = re.sub(r'[.\-\']', ' ', n)
    n = re.sub(r'\s+', ' ', n)
    return n


# Build normalized IPL lookup: normalized_name -> team_abbr
ipl_lookup = {}
for team, players in IPL_SQUADS.items():
    for p in players:
        ipl_lookup[normalize(p)] = team

# Explicit overrides for fantasy names that differ from IPL website names
NAME_TO_IPL = {
    "AM Ghazanfar": "MI",
    "Arjun Sachin Tendulkar": "LSG",
    "Auqib Nabi Dar": "DC",
    "Digvesh Singh Rathi": "LSG",
    "Lungi Ngidi": "DC",
    "M Shahrukh Khan": "GT",
    "Manimaran Siddharth": "LSG",
    "Philip Salt": "RCB",
    "Praveen Dubey": "PBKS",
    "Rasikh Salam Dar": "RCB",
    "Ravisrinivasan Sai Kishore": "GT",
    "Shahbaz Ahmed": "LSG",
    "T Natarajan": "DC",
    "Vijaykumar Vyshak": "PBKS",
    "Mohammed Shami": "LSG",
    "Raj Bawa": "MI",
    "Mitchell Owen": "PBKS",
    "Mohd. Arshad Khan": "GT",
    "Aryan Juyal": "MI",
    "Vaibhav Suryavanshi": "RR",
    "Suryansh Shedge": "PBKS",
}

TEAM_FULL_NAMES = {
    "CSK": "Chennai Super Kings",
    "DC": "Delhi Capitals",
    "GT": "Gujarat Titans",
    "KKR": "Kolkata Knight Riders",
    "LSG": "Lucknow Super Giants",
    "MI": "Mumbai Indians",
    "PBKS": "Punjab Kings",
    "RCB": "Royal Challengers Bengaluru",
    "RR": "Rajasthan Royals",
    "SRH": "Sunrisers Hyderabad",
}

# Load teams_data.json
with open('teams_data.json') as f:
    data = json.load(f)

# Build players database
players_db = {}
unmatched = []

for team_name, team_info in data['teams'].items():
    for p in team_info['players']:
        name = p['name']
        cricbuzz_id = p['cricbuzz_id']

        # Determine IPL team
        ipl_team = None

        # Check explicit overrides first
        if name in NAME_TO_IPL:
            ipl_team = NAME_TO_IPL[name]
        else:
            # Try normalized match
            norm = normalize(name)
            if norm in ipl_lookup:
                ipl_team = ipl_lookup[norm]

        if ipl_team is None:
            unmatched.append(name)

        # Build player entry
        player_entry = {
            "name": p['name'],
            "cricbuzz_id": cricbuzz_id,
            "role": p['role'],
            "country": p['country'],
            "ipl_team": TEAM_FULL_NAMES.get(ipl_team, "Unknown") if ipl_team else "Unknown",
            "ipl_team_short": ipl_team or "Unknown",
            "fantasy_owners": [],
            "price": p['price'],
        }
        if 'original_name' in p:
            player_entry['original_name'] = p['original_name']

        # Add fantasy owner (handle duplicates across fantasy teams)
        if cricbuzz_id in players_db:
            if team_name not in players_db[cricbuzz_id]['fantasy_owners']:
                players_db[cricbuzz_id]['fantasy_owners'].append(team_name)
        else:
            player_entry['fantasy_owners'].append(team_name)
            players_db[cricbuzz_id] = player_entry

# Print stats
print(f"Total players in DB: {len(players_db)}")
print(f"Unmatched players: {len(unmatched)}")
if unmatched:
    for u in sorted(set(unmatched)):
        print(f"  UNMATCHED: {u}")

# Count by IPL team
ipl_counts = Counter(p['ipl_team_short'] for p in players_db.values())
print("\nPlayers per IPL team:")
for team, count in sorted(ipl_counts.items()):
    full = TEAM_FULL_NAMES.get(team, team)
    print(f"  {team:8s} ({full}): {count}")

# Save
with open('players_data.json', 'w') as f:
    json.dump({"players": players_db}, f, indent=2)
print(f"\nSaved players_data.json with {len(players_db)} players")
