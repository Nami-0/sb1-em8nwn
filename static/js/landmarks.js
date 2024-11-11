// Valid landmarks dictionary
const VALID_LANDMARKS = {
    'japan': [
        'tokyo tower', 'mount fuji', 'sensoji temple', 'shibuya crossing',
        'tokyo skytree', 'osaka castle', 'fushimi inari shrine', 'nintendo world',
        'akihabara', 'harajuku', 'shinjuku', 'imperial palace', 'meiji shrine',
        'tsukiji market', 'odaiba', 'ueno park', 'tokyo disneyland',
        'arashiyama bamboo forest', 'kinkaku-ji', 'nara park', 'dotonbori',
        'himeji castle', 'tokyo dome', 'roppongi'
    ],
    'france': [
        'eiffel tower', 'louvre museum', 'notre dame cathedral', 'arc de triomphe',
        'versailles palace', 'champs elysees', 'mont saint michel', 'moulin rouge',
        'sacre coeur', 'disneyland paris', 'musee dorsay', 'le marais',
        'palace of versailles', 'french riviera', 'nice', 'monaco', 'saint tropez',
        'normandy beaches', 'loire valley', 'bordeaux', 'french alps'
    ],
    'united_states': [
        'statue of liberty', 'times square', 'central park', 'golden gate bridge',
        'hollywood sign', 'disney world', 'grand canyon', 'white house',
        'universal studios', 'broadway', 'empire state building', 'alcatraz',
        'fishermans wharf', 'space needle', 'las vegas strip', 'mount rushmore',
        'yellowstone', 'french quarter', 'venice beach', 'navy pier'
    ],
    'china': [
        'great wall', 'forbidden city', 'terracotta army', 'temple of heaven',
        'summer palace', 'west lake', 'oriental pearl tower', 'victoria harbour',
        'hong kong disneyland', 'giant panda base', 'zhangjiajie', 'huangshan',
        'nanjing road', 'the bund', 'yu garden', 'tiananmen square', 'canton tower',
        'potala palace', 'yellow mountain', 'mogao caves'
    ],
    'australia': [
        'sydney opera house', 'bondi beach', 'great barrier reef', 'ayers rock',
        'melbourne cricket ground', 'harbour bridge', 'gold coast', 'daintree rainforest',
        'great ocean road', 'phillip island', 'kings park', 'cable beach',
        'twelve apostles', 'federation square', 'port arthur', 'kakadu national park',
        'blue mountains', 'surfers paradise', 'byron bay', 'rottnest island'
    ],
    'united_kingdom': [
        'big ben', 'tower bridge', 'buckingham palace', 'london eye',
        'tower of london', 'westminster abbey', 'stonehenge', 'edinburgh castle',
        'royal mile', 'loch ness', 'giants causeway', 'lake district',
        'windsor castle', 'oxford university', 'roman baths', 'york minster',
        'hadrians wall', 'peak district', 'cambridge university', 'cotswolds'
    ],
    'thailand': [
        'grand palace', 'wat phra kaew', 'wat arun', 'khao san road',
        'phi phi islands', 'sukhumvit', 'chatuchak market', 'ayutthaya',
        'doi suthep', 'railay beach', 'floating market', 'wat pho',
        'erawan waterfall', 'similan islands', 'phang nga bay', 'maya bay',
        'sukhothai', 'big buddha phuket', 'koh samui', 'khao yai'
    ],
    'singapore': [
        'marina bay sands', 'gardens by the bay', 'sentosa', 'universal studios',
        'orchard road', 'clarke quay', 'merlion park', 'singapore zoo',
        'chinatown', 'botanic gardens', 'night safari', 'little india',
        'singapore flyer', 'jurong bird park', 'arab street', 'raffles hotel',
        'national gallery', 'esplanade', 'pulau ubin', 'fort canning'
    ]
};
