import csv

# Known movies in our library where an official 4K UHD physical disc release exists in the wild
KNOWN_4K_EXISTS = {
    "True Lies",
    "Terminator 2 Judgment Day",
    "The Bridge on the River Kwai",
    "Blow-Up",
    "Apocalypse Now",
    "Dog Day Afternoon",
    "Vertigo",
    "The Seventh Seal",
    "The Graduate",
    "Lost in Translation",
    "Daisies",
    "Kung Fu Hustle",
    "Battle Royale",
    "Under the Skin",
    "Cape Fear",
    "Chungking Express",
    "Death Becomes Her",
    "The Long Goodbye",
    "The Presidio",
    "Nashville",
    "Badlands",
    "Rio Lobo", # Kino Lorber 4K UHD
    "The House That Jack Built", # Curzon 4K UHD
    "Melancholia", # Curzon 4K UHD
    "Antichrist", # Curzon 4K UHD
    "A Place in the Sun", # Paramount Presents 4K UHD
    "Angst", # Cult Epics 4K UHD
    "Nights of Cabiria", # StudioCanal 4K UHD
    "Written on the Wind", # Criterion 4K UHD
    "Magnificent Obsession", # Criterion 4K UHD
    "Brief Encounter", # Criterion 4K UHD
    "Bigger than Life", # BFI 4K UHD
    "Days of Being Wild", # Criterion 4K UHD
    "2046", # Criterion 4K UHD
    "Fallen Angels", # Criterion 4K UHD
    "Nobody Knows", # 4K restored / 4K release
    "After Life", # Criterion 4K UHD
    "Shoplifters", # Magnolia / Le Pacte 4K UHD
    "The Chaser", # Arrow 4K UHD
    "The Yellow Sea", # Arrow 4K UHD
    "Imitation Of Life", # Criterion 4K UHD
    "Red Desert", # Criterion 4K UHD
    "Kwaidan", # Eureka Masters of Cinema 4K UHD
    "Doberman Cop", # Arrow 4K UHD
    "Shadows of Forgotten Ancestors", # 4K restored
    "Lolita", # Warner / Criterion 4K
    "The Sorrow and the Pity", # Arrow 4K UHD
    "The End of Evangelion", # 4K UHD
    "Lancelot of the Lake", # 4K restored
}

# Sub-optimal (DVD / 576p / Web-DL where 1080p bluray exists)
SUB_OPTIMAL_TITLES = {
    "A Spring for the Thirsty", # 576p DVD
    "The Legend of Princess Olga", # 576p DVD
    "The Eve of Ivan Kupalo", # 576p DVD
}

def evaluate_quality_tier(quality_str: str, title: str):
    q_lower = quality_str.lower()
    
    # 1. 4K UHD Remux (Already the best quality available)
    if "4k" in q_lower or "2160p" in q_lower or "uhd" in q_lower:
        return "⭐ Yes (4K UHD)"
    
    # 2. Lower tier (DVD / 576p)
    if "dvd" in q_lower or "576p" in q_lower or title in SUB_OPTIMAL_TITLES:
        return "🔻 Higher Tier Exists"
        
    # 3. 1080p Remux: check if a 4K UHD disc exists in the wild
    if title in KNOWN_4K_EXISTS:
        return "⚠️ 4K UHD Exists"
    
    # 4. 1080p Remux is the best available (no 4K disc exists in the world)
    return "🟢 Yes (1080p Best)"

if __name__ == "__main__":
    with open("remux_library.csv", "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        
    stats = {}
    for r in rows:
        tier = evaluate_quality_tier(r["Quality"], r["Title"])
        stats[tier] = stats.get(tier, 0) + 1
        
    print("Quality Tier Evaluation across 393 titles:")
    for k, v in stats.items():
        print(f"  {k:25s}: {v} titles")
