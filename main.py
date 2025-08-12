import datetime
import os

import google.generativeai as genai
from discord import Message
from dotenv import load_dotenv

load_dotenv()

gemini_api_key = os.getenv('GEMINI_API_KEY')
genai.configure(api_key=gemini_api_key)


def generate_response(user_input, system_instruction, model="gemini-2.5-pro-exp-03-25", generation_config=None,
                      safety_settings=None):
    print("generating response")
    if not generation_config:
        generation_config = {
            "temperature": 0.5,
        }
    if not safety_settings:
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE"
            },
        ]

    model = genai.GenerativeModel(model_name=model,
                                  generation_config=generation_config,
                                  system_instruction=system_instruction,
                                  safety_settings=safety_settings)
    convo = model.start_chat(history=[
    ])
    convo.send_message(user_input)
    print(convo.last.text)
    return convo.last.text


import discord
from datetime import datetime, timedelta, timezone


async def split_messages_by_hours(messages, hours_split):
    """Split messages into two lists: one from the first hours_split hours and the other with the rest."""

    # Get the current time in UTC
    now = datetime.now(timezone.utc)

    # Calculate the time threshold for hours_split (e.g., 48 hours ago)
    time_threshold = now - timedelta(hours=hours_split)

    # Lists to store split messages
    first_list = []
    second_list = []

    # Iterate over the messages
    for message in messages:
        if message.created_at > time_threshold:
            # Message is within the first hours_split hours
            first_list.append(message)
        else:
            # Message is older than hours_split
            second_list.append(message)

    return first_list, second_list


# Your Discord token here (user token from the browser's developer tools)
TOKEN = os.getenv('DISCORD_USER_TOKEN')

# specify the user id of the discord account being able to control the bot
controller_id = os.getenv('CONTROLLER_ID')

# if the bot account can use the commands
can_bot_control_itself = True

# specify the user id of the discord account being able to control the bot
controller_channel_id = os.getenv('CONTROLLER_CHANNEL_ID')

# Define the first day of the Gaiartian calendar
first_day = datetime(2022, 9, 1)

# Gaiartian months
months = ["Gaiarkhè", "Tempopidum", "Quinésil", "Éposendre"]

hours_to_summarize = int(os.getenv('HOURS_TO_SUMMARIZE'))
context_hours = int(os.getenv('HOURS_OF_CONTEXT'))
starting_hour = int(os.getenv('STARTING_HOUR'))


def calculate_gaiartian_date(input_date: str):
    """Convert real-world date into custom Gaiartian date format."""
    try:
        date = datetime.strptime(input_date, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return "Invalid date format. Please use %Y-%m-%d %H:%M:%S"

    # Calculate the number of months since the first day
    n_months_since_first_day = (date.year - first_day.year) * 12 + (date.month - first_day.month)

    # Calculate the Gaiartian year
    year = (n_months_since_first_day // 4) + 1
    if year <= 0:
        year -= 1  # There is no year 0 in the Gaiartian calendar

    # Calculate the Gaiartian month
    month_index = (date.month - 1) % len(months)
    month = months[month_index]

    # Extract the day
    day = date.day

    # Return the Gaiartian date as a formatted string
    return year, day, month  # Return the components separately for flexible formatting


class MyClient(discord.Client):
    async def on_ready(self):
        print('Logged on as', self.user)

    async def on_message(self, message: Message):
        # check if the message is from the controller id or the bot if allowed
        if (can_bot_control_itself and message.author.id == self.user.id) or (
                str(message.author.id) == str(controller_id)):
            if str(message.channel.id) == str(controller_channel_id):
                if message.content == "$summarize":
                    summary = await self.summarize(message)
                if message.content == "$journal":
                    summary = await self.journal(message)

    async def get_messages_since_last_x_hours(self, channel_id, hours):
        """Fetch and return all messages in a specific channel from the last X hours, excluding messages newer than starting_hour."""
        channel = self.get_channel(channel_id)
        if not channel:
            print(f"Channel with ID {channel_id} not found.")
            return []

        # Calculate the time thresholds and make them timezone-aware in UTC
        now = datetime.now(timezone.utc)
        time_threshold = now - timedelta(hours=hours)
        start_time_threshold = now - timedelta(hours=starting_hour)

        # List to store messages (raw)
        all_messages = []

        # Fetch the messages from most recent to oldest
        async for message in channel.history(limit=None):  # limit=None fetches all available messages
            if message.created_at < time_threshold:
                break
            if message.created_at > start_time_threshold:
                continue
            all_messages.append(message)

        # Reverse the list to make it from oldest to newest
        all_messages.reverse()

        return all_messages
    async def format_message(self, message):
        """Format a single message with username, Gaiartian date, and content, replacing mentions."""
        content = message.content

        # Replace user mentions with actual usernames
        for user in message.mentions:
            content = content.replace(f'<@{user.id}>', f'@{user.display_name}')

        # Replace channel mentions with actual channel names
        for channel in message.channel_mentions:
            content = content.replace(f'<#{channel.id}>', f'#{channel.name}')

        # Convert message.created_at to a string format to use in Gaiartian date conversion
        message_time_str = message.created_at.strftime("%Y-%m-%d %H:%M:%S")

        # Get Gaiartian date components (year, day, month)
        year, day, month = calculate_gaiartian_date(message_time_str)

        # Get the time part (hours, minutes, seconds)
        time_part = message.created_at.strftime("%H:%M:%S")

        # Format message in "[An X, le DAY de month_name à time]: message content" format
        formatted_message = f"{message.author.display_name} [An {year}, le {day} de {month} à {time_part}]:\n{content}"

        return formatted_message

    async def summarize(self, message):

        # Fetch raw messages for géopolitique channel
        messages_géopolitique = await self.get_messages_since_last_x_hours(718824042685136936, context_hours)
        # Split messages into those to summarize and context messages
        messages_to_summarize_géopolitique, messages_as_context_géopolitique = await split_messages_by_hours(
            messages_géopolitique, hours_to_summarize)
        # Format messages after splitting
        messages_to_summarize_géopolitique = [await self.format_message(m) for m in
                                              messages_to_summarize_géopolitique]
        messages_as_context_géopolitique = [await self.format_message(m) for m in
                                            messages_as_context_géopolitique]

        # Fetch raw messages for annonces channel
        messages_annonces = await self.get_messages_since_last_x_hours(1017475737852317768, context_hours)
        # Split messages into those to summarize and context messages
        messages_to_summarize_annonces, messages_as_context_annonces = await split_messages_by_hours(
            messages_annonces,
            hours_to_summarize)
        # Format messages after splitting
        messages_to_summarize_annonces = [await self.format_message(m) for m in
                                          messages_to_summarize_annonces]
        messages_as_context_annonces = [await self.format_message(m) for m in messages_as_context_annonces]

        system_message = f"""Tu seras un Agent dont le but est de résumé des évènements de salons RPs d'un salon discord dans un format tel que les résumés puissent être automatiquement ajoutés à une page fandom. Le serveur discord est le serveur discord d'un serveur minecraft nommé LaBoulangerie qui est un serveur géopolitique semi-rp. Tu résumeras le contenu du salon #géopolitique qui est le salon pour rp et faire de la géopolitique, mais tu résumeras aussi le salon #annonces qui est le salon des annocnes rp et géopolitiques, des villes, nations, entreprises, roganisations, joueurs etc... Tu seras donné la liste des messages des {hours_to_summarize} dernières heures à résumés. Chaque message aura son auteur, sa date, et son contenu textuel. Tu seras aussi donné en contexte, les messages des 7 précédents jours, mais eux ne seront pas à résumés, résume seulement ceux des {hours_to_summarize} (qui te seront donnés séparemment."
    Le format d'un message sera 'author_name [date]: message_content' with [date] being in the format [An X, le DAY_NUMBER de CUSTOM_MONTH_NAME à TIME_IN_HOURS_MINUTES_SECONDS] parce que oui Gairtos utilise seulement 4 mois customs : Gaiarkhè, Tempopidum, Quinésil, Éposendre
    Dans le Fandom, chaque An a sa propre page, et dedans à un moment il y a les évènements dans un ordre chronologique. Je vais te donner comme example le wikicode de la page de l'An 4 , regarde bien comment il est formatté. Tu devras seulement créer des tirets pour des évèhnements à des dates. Tu devras faire un tiret (et donc résumé) par jour donné, voici le wikicode complet de la page :
    L''''an 4''' est une année tertiaire du Calendrier Gaiartois qui commence un vendredi. Elle fait suite à l'[[an 3]] et précède l'[[an 5]].

    Elle correspond à l'an 2003 du [[Calendrier Panimorphe]] et les mois de septembre à décembre 2023 du [[Calendrier Minecraftien]].
    ```
    ==Événements==
    ===Gaiarkhè===

    * 6 gaiarkhè, [[Kætern d'Ange]] fonde [[Dolivageä]].
    * 9 gaiarkhè, [[Dolivageä]] adopte la [[:Fichier:Bannière de Dolivageä.png|Bannière de Dolivageä]].
    * 10 gaiarkhè, [[Algard]] cède une partie de ses terres du nord à [[Dolivageä]] suite à un entretien entre [[Valgard Arkisson|Valgard Arkinsson]] et [[Kætern d'Ange]].
    * 16 gaiarkhè
    ** [[Dolivageä]] adopte le [[:Fichier:Blason de Dolivageä.png|Blason de Dolivageä]].
    ** [[Dolivageä]] inaugure le [[Temple du Rubis]] et annonce sa participation au [[concours de patrimoine]] de la [[Panitropole]].
    * 17 gaiarkhè
    ** [[Red 1er|Red Ier]] et [[Kætern d'Ange]] signent le [[Traité de Dolivageä]].
    ** [[Kætern d'Ange]] fonde le [[Duché de Dolivageä]] qui adopte la [[:Fichier:Bannière de Dolivageä.png|Bannière]] et le [[:Fichier:Blason de Dolivageä.png|Blason de Dolivageä]].
    *21 gaiarkhè, le [[Duché de Dolivageä]] et sa [[Dolivageä|préfecture]] adoptent leur devise officielle « [[Nos louanges se chantent en Arthos]] ».
    * 28 gaiarkhè, [[Dolivageä]] et [[Cushy]] inaugurent [[le Prismarin]].

    ===Tempopidum===

    * 1ᵉʳ tempopidum
    ** [[PainOraisins]] décode l'énigme de [[Fryzhen]].
    ** [[Léonard Vizzini]] meurt dans un attentat commis, selon [[Goldcrest]], par des militants [[Familisme|familistes]].
    ** [[Adrian Hartmann]] publie l'essai [[Réflexion sur l'Illusion du Bien Commun]].
    ** Le [[Nalvarune|Royaume de Nalvarune]] adopte un régime oligarchique, [[Sir Matthew Percival Norrington|Matthew Norrington]], [[François LeNoble]] et [[Valérian "Caesar" Nerona|Valérian Nerona]] sont nommés [[Oligarque de Nalvarune|oligarques de Nalvarune]].
    *3 tempopidum
    **Le [[Petit Gaiartois]] publie le dixième numéro de [[Petit Gaiartois (journal)|son hebdomadaire]].
    **[[Zagrivocha]] répond à l'annonce de l'assassinat de [[Léonard Vizzini]] en la remettant en cause et en condamnant l'attentat, et dénonce le traitement de l'affaire par le [[Petit Gaiartois]].
    *5 tempopidum
    **Le [[Petit Gaiartois]] répond à la réponse de [[Zagrivocha]] en la traitant comme une menace, annonce une édition spéciale sur les [[attentats des routes du Nether]] et lance un sondage sur l'augmentation du prix de [[Petit Gaiartois (journal)|son hebdomadaire]].
    **[[Zagrivocha]] répond de nouveau au [[Petit Gaiartois]] en expliquant ne pas la menacer.
    * 10 tempopidum, le [[Petit Gaiartois]] publie le onzième numéro de [[Petit Gaiartois (journal)|son hebdomadaire]].
    * 11 tempopidum
    ** [[Marc Lèone]] fonde l'[[Île-Croissant Souveraine]] sur l'[[Île-Croissant|île éponyme]] ou s'installe la [[Congrégation de la Chape|Congrégation de la Chappe]] après avoir pillé une partie des ressources d'[[Annales d'Augolia|Augolia]].
    ** Le [[Parti Kæterniste]], dans le cadre de son combat contre le [[familisme]], publie l'[[affiche anti-familiste]] qu'elle fait mettre en vente à l'aide de la [[Fondation d'Ange]]. Il annonce travailler sur une proposition de premier [[Code Pénal du Royaume de Goast]], où serait interdit la « propagation des idées familistes ».
    *12 tempopidum
    **[[Kætern d'Ange]] lance le premier appel d'offre pour le chantier du [[Château de Dolivageä]].
    **[[Ludovicus Ventor]] érige la route entre [[Cushy]] et [[Nalvarune]].
    **[[Louis-Philippe Vizzini|Louis-Philippe Vizzini Iᵉʳ]] fonde le [[Parti Capitaliste Gaiartois]].
    **[[Giga Zeus]] rend publique son usine à trident.
    *13 tempopidum
    **[[MMMOK]] pille [[Osharia]] puis rejoint [[Nalvarune]].
    **[[Nalvarune]] adopte la [[Constitution de Nalvarune]].
    **[[Louis-Philippe Vizzini|Louis-Philippe Vizzini Iᵉʳ]] annonce les avancées de l'enquête sur l'[[Assassinat de Léonard Vizzini]], les auteurs du meurtre semblent décédés et d'origines [[Annales d'Augolia|augoloises]].
    *14 tempopidum
    **[[MMMOK]] pille [[Nalvarune]] avant de se faire tuer par [[Lengevin]].
    **[[Friolon|Friolon d'Orion]] organise la [[Congrégation des Marchands de Damield]] a [[Osterces]].
    *15 tempopidum
    **[[Kætern d'Ange]] trouve le cadavre de [[Tortamor]] et les [[journaux de Maximus]] après l'annonce de [[Cushy]]. Il y rencontre [[Maximus Maledictio]] et s'engage dans un combat avec, il finira par fuir avec les journaux en voyant la puissance de Maximus.
    **[[Maximus Maledictio]] attaque les [[routes du Nether]] avec une armée de withers, il y rencontre [[Louis-Philippe Vizzini|Louis-Philippe Vizzini Iᵉʳ]] qu'il tue lors d'un combat.
    **Un inconnu rase la fontaine du [[Cushy|quartier pauvre de Cushy]] lors d'une réunion au [[Panitropole|forum de la Panitropole]].
    **[[Endafyr Quamat]] annonce le repos de [[Kætern d'Ange]] à [[Cushy]] suite à une blessure subie lors de son combat contre [[Maximus Maledictio]].
    *16 tempopidum
    **[[Louis-Philippe Vizzini 2ème|Louis-Philippe Vizzini II]] devient maire de [[Goldcrest]].
    **Le [[Nalvarune|Royaume de Nalvarune]] modifie sa constitution pour y ajouter l'article concernant la Chancelière.
    **[[Gabrielle de Marliave]] est nommée Chancelière du [[Nalvarune|Royaume de Nalvarune]] par les Oligarques.
    **Le [[Nalvarune|Royaume de Nalvarune]] met en place sa vigilance attentat suite à l'[[attaque de Maximus Malédictio]].
    *18 tempopidum, [[Maximus Maledictio|Maximus Malédictio]] fait quelques apparitions à [[Zagrivocha]] et [[Nalvarune]].
    *20 tempopidum
    **[[Adrian Hartmann]] annonce chercher un emplacement pour l'[[Université de Clover]].
    **La [[Fondation d'Ange]] met en place le Fond Solimiste.
    *23 tempopidum
    **Osterces inaugure la Bibliothèque de la Congrégation de la Chape.
    **[[Maximus Maledictio]] fait une apparition à [[Annales d'Augolia|Augolia]].
    *24 tempopidum, le [[Petit Gaiartois]] publie le douzième numéro de [[Petit Gaiartois (journal)|son bihebdomadaire]].
    *25 tempopidum
    **Le [[Duché de Dolivageä]] inaugure le [[Pont Louis-Philippe Ier]] et la route entre [[Dolivageä]] et les [[ruines d'Asgardia]].
    **[[Nalvarune]] entame des fouilles archéologiques à son lac.
    **[[Valgard Arkisson|Valgard Arkinsson]] expose ses deux premières gravures a [[Algard]].
    *27 tempopidum, [[Louis-Philippe Vizzini II]] fonde la [[Vizzini Print]].
    *30 tempopidum [[Maximus Maledictio]] fait une apparition à [[Hernebhes des Solimes|Solimé]], par la suite, il tue [[Matzepol]], le meurtre est dénoncé par [[Nalvarune]] dans la foulée.
    *31 tempopidum, [[Cushy]] met la tête de [[Maximus Maledictio]] à prix.
    ===Quinésil===

    * 1er quinésil, [[Osterces]] inaugure la [[Tour d'Yggdrasil]].
    * 2 quinésil, [[Osterces]] inaugure le [[café de l'Antique]].
    * 3 quinésil, [[Osterces]] inaugure la route la reliant aux [[ruines d'Asgardia]].
    * 4 quinésil
    ** [[Revax]] fonde le parti des [[Partageurs Gaiartois Unis]] et distribue des tracs exposant son programme et annonçant vouloir détruire les symboles du [[Royaume de Goast]] dont les routes, ce tract provoque une polémique au sein du Royaume.
    ** [[Dolivageä]] proclame hors-la-loi [[Revax]] et [[le Vagabond]] pour leur proximité avec l'idéologie [[Familisme|familiste]].
    ** La résidence [[Le Vagabond|du Vagabond]] a [[Solimé]] est perquisitionnée par les autorités goasts.
    ** [[Bidouille Dierne]] fonde la [[Bidouille Building Company]].
    ** La [[Société Vizzini]] organise une soirée d'inauguration pour son restaurant le [[Vizzini d'Or]].
    ** Le [[Nalvarune|Royaume de Nalvarune]] annonce avoir décodé les messages de [[Maximus Maledictio]].
    ** La résidence de [[Revax]] a [[Solimé]] est perquisitionnée par les autorités goasts.
    *6 quinésil - [[Le Renard]] mène un coup d'état dans [[la retraite du Démon]] qu'il réussi et assassine [[Bleu Azure]].

    ===Éposendre===
    ```

    Je le répète, toi devras juste ajouté des dates individuelles, et si besoin les évènements individuels. Car un résumé d'un jour peut avoir plusieurs choses (c'est même probable).
    Le type d'évènement doit être un minimum important, comme tu le vois ici.
    Voici d'autres examples de pages d'An pour que tu comprennes quels types d'évènements sont gardés :
    ```
    L''''an 5''' est une année tertiaire du [[Calendrier Gaiartois]] qui commence un vendredi. Elle fait suite à l'[[an 4]] et précède l'[[an 6]].

    Elle correspond à l'an 2004 du [[Calendrier Panimorphe]] et les mois de janvier à avril 2024 du [[Calendrier Minecraftien]].
    ==Événements==
    ===Gaiarkhè===

    * 2 gaiarkè, le [[Shade]] annonce la tenue du duel entre lui-même et [[Louis-Philippe Vizzini 2ème|Louis-Philippe Vizzini II<sup>ème</sup>]].
    *6 gaiarkhè
    **[[Royaume de Goast|Goast]] rend son indépendance à [[Veltea]].
    **[[Louis-Philippe Vizzini 2ème|Louis-Philippe Vizzini II<sup>ème</sup>]] bat le [[Shade]] en duel dans le cadre du [[Shade#Légende du Cristal (Depuis le 22 éposendre de l'an 4)|Défi du Shade]].
    *7 gaiarkhè
    **[[Veltea]] s'effondre et [[Algard]] en prend le contrôle créant une polémique.
    **[[Végétalia]] s'effondre.
    *8 gaiarkhè, [[Algard]] cède le contrôle de [[Veltea]].
    *9 gaiarkhè
    **[[Alster]] prend le contrôle de [[Veltea]].
    **[[Kætern d'Ange]] annonce la tenue d'enchères au [[Château de Dolivageä]].

    *14 gaiarkhè, création de la Fédération Familiste de Brulfroï après un rapprochement entre les deux pays de Kappi et de Zagrivocha.
    *20 gaiarkhè
    **Enchères à [[Dolivageä|Dolivagëa]]. Le [[royaume de Goast]] accuse [[Royaume de Nalvarune|Nalvarune]] d'avoir menti sur la rareté des dromadaires vendus ainsi que [[Vindicta]] d'avoir manipulé les prix en surenchérissant les lots<ref>[[https://discord.com/channels/516302751500599316/1017475737852317768/1198681122247286804|Annonce officielle du 21 janvier]]</ref>.
    **[[Ormick Ier|Ormick I<sup>er</sup>]] prend le trône vacant à [[Vicciopolis]] et dans la [[coprincipauté d'Hybloniopolis]], confirmant l'union personnelle entre les deux cité-États.

    * 24 gaiarkhè, érection d'une première Grande Tour Magique de Gaiartos, l'Aegeria, à Osterces.

    *26 gaiarkhè, inauguration de la bibliothèque à [[Cushy]].

    ===Tempopidum===

    *3 tempopidum, [[Jorvik]] (aujourd'hui Poséage) rejoint le [[royaume de Goast]] pour la commémoration des 1 an de la fin de la [[Guerre des Quatre Armées]] dans le musée de [[Tharass]].
    *11 gaiarkhè
    **Début de la publication posthume de l'œuvre ''De la démocratie en Gaiartos'' de [[Mazer O’Shaw|Mazer O'Shaw]].
    **Friolon II prend la relève après que le précédent souverain d'[[Osterces]] ait été tué dans des « circonstances douteuses »<ref>[[https://discord.com/channels/516302751500599316/1017475737852317768/1206304677335924776|Annonce de la ville d'Osterces]] du même jour :« C'est depuis Osterces, que je vous parle : moi, Friolon deuxième du nom, prend la relève de la direction de la ville. En effet, notre précédent souverain et fondateur est décédé en de douteuses circonstances.  » </ref>.

    *12 gaiarkhè, le [[Azurentos|duché d'Azurentos]] déclare son indépendance du [[royaume de Nalvarune]], créant le [[royaume d'Astréa]], qui provoque une crise interne à Nalvarune.
    *17 gaiarkhè, organisation du concours quadriennal de course des bateaux de glace dans la [[Fédération Familiste de Bulfroi|F.F.B.]]
    *21 gaiarkhè, pousse de l'« Arbre de vie » à Algard sur lequel le Jarl a étendu sa résidence afin d'en apprendre davantage<ref>[[https://discord.com/channels/516302751500599316/1017475737852317768/1209967995649007656|Annonce de la ville d'Algard]] du même jour</ref>.
    *23 tempopidum, mariage entre [[Ormick Ier|Ormick I<sup>er</sup>]] et [[Louis-Philippe Vizzini 2ème|Louis-Philippe Vizzini II<sup>ème</sup>]] à [[Vicciopolis]].
    *21 tempopidum, ouverture des candidatures pour l'élection des Grands Jurés du Comité des Brasseurs afin de revitaliser l'organisation<ref>[[https://discord.com/channels/516302751500599316/1017475737852317768/1210219857090576437|Annonce du Comité]] le jour même</ref>.
    *25 tempodidum, fondation du [[royaume de Crusentia]] avec le maire d'[[Osharia]], les titulaires des trônes d'[[Coprincipauté d'Hybloniopolis|Hybloniopolis]] et de [[Vicciopolis]] et le maire de la cité-État de [[Cushy]].
    *25 tempopidum, naissance des enfants de [[Ormick Ier|Ormick I<sup>er</sup>]] et [[Louis-Philippe Vizzini 2ème|Louis-Philippe Vizzini II<sup>ème</sup>]] : Louis-Philippe Vizzini O'Shaw I<sup>er</sup> ''Junior'' et Emarant Vizzini O'Shaw I<sup>er</sup> ''Junior''
    *28 tempopidum
    **Aésultats des élections au [[Comité des Brasseurs]] : [[Nicolas Junlase]], [[Ruki tamashi|Ruki Tamashi]] et [[Ormick Ier|Ormick I<sup>er</sup>]] deviennent Grands Jurés.
    **Abdication du [[Guillaume Verentti Garois|Guillaume Garois I<sup>er</sup>]] en faveur de son fils [[Gaëtan Guillaume Garois|Gaëtan Garois II]] qui monte sur le trône à [[Astréa]].

    ===Quinésil===

    *2 quinésil, nouvelles attaques sur les routes nétheresques.
    *3 quinésil
    **Mort de [[Nicolas Junlase]].
    **Disparition de ReNouy, voleur connu.

    *4 quinésil, 
    **Azurentos commercialise de la vodka black et du vin lumineux, vente condamnée par le Comité des Brasseurs qui fait proposer la guerre contre Azurentos au Conseil Constitutionnel de Goast.<ref>https://discord.com/channels/516302751500599316/718824042685136936/1214185513477480468</ref>
    **Création [[Rassemblement des Saveurs Brassicole]] par le roi [[Gaëtan Guillaume Garois|Gaëtan Garois II]] en réponse à « [l'impossibilité] d'exploiter [ces] boisson[s] à moins d'en être le breveté »<ref>[[https://discord.com/channels/516302751500599316/1017475737852317768/1214009565323198484|Annonce officielle de l'organisation]]</ref>.
    *6 quinésil, création de la [[guilde des Marchands]] par [[Louis-Philippe Vizzini 2ème|Louis-Philippe Vizzini II<sup>ème</sup>]].
    *13 quinésil, annonce d'une collaboration entre le [[royaume de Goast]] et la [[Fédération Familiste de Bulfroi|F.F.B.]] pour la surveillance de l'exploitation des glaciers du nord, ainsi qu'une collaboration entre ce même royaume et la [[principauté d'Augolia]] pour revégétaliser et protéger l’environnement des [[Iles-de-Fer]].
    *17 quinésil, tenue d'enchères pour l'inauguration du château de [[Tharass]].
    *24 quinésil
    **Effondrement de la ville du [[royaume de Nalvarune]] suite aux problèmes internes due aux sécessionnistes d'Azurentos.
    **La famille royale excepté le roi [[Gaëtan Guillaume Garois|Gaëtan Garois II]] se retire pour construire une villégiature près de [[Nalvarune]] afin de protéger les ruines de la ville.
    *29 quinésil
    **Début de construction d'un quartier résidentiel à [[Osterces]].
    **Signature du [[traité de Vicciopolis]] pour le libre échange entre le [[royaume de Goast]] et le [[royaume de Crusentia]].

    ===Éposendre===

    *1<sup>er</sup> éposendre
    **Mort du roi [[Gaëtan Guillaume Garois|Guillaume Garois I<sup>er</sup>]] et explications de la nouvelle constitution du [[royaume d'Astréa]] avec un pouvoir monarchique absolu et un Sénat consultatif, ainsi que présentation du culte astréen.
    **Canulars du 1<sup>er</sup> avril.
    **Mariage de [[Red 1er|Red I<sup>er</sup>]] et [[Friolon|Magelion d'Orion II]] lors duquel l'ex-roi décède accidentellement. Création d'une journée nationale en [[Royaume de Goast|Goast]] et vague de soutiens internationaux lors de son annonce le 3 éposendre.
    **Effondrement de [[Midgard]], qui est pillée par Algard puis les ressources de laquelle son rendue à son nouveau suzerain : [[Coprincipauté d'Hybloniopolis|Hybloniopolis]].

    *2 éposendre, [[Tajir Pa'an]] déclare la [[Commune d'Azurentos]] tandis que la famille royale s'est absentée, commençant la [[crise azurentoise]].
    *3 éposendre, création de la Légion étrangère gaiartoise par le roi [[Gaëtan Guillaume Garois|Gaëtan Garois II]]
    *4 éposendre, érection d'une statue en l'honneur du défunt Red I<sup>er</sup>.
    *5 éposendre
    **La couronne azurentoise déclare l'État d'urgence et la répression anti-insurrection.
    **Annonce des échecs des pourparlers sous l'égide d'[[Industrial-Town]] entre les deux parties impliquées à cause du refus de la couronne azurentoise.

    *6 éposendre, 
    **La Panitropole appelle les gaiartois à l'aider pour construire un nouveau port, l'[[évent du port]].
    **Propositions de pourparlers par la couronne azurentoise, refusée par [[Tajir Pa'an]].

    *10 éposendre,
    **Proposition de création de l'''Indestructi'Banque'' par [[Friolon|Magelion d'Orion II]].
    **Cushy déclare revendiquer la presque intégralité des territoires anciennement détenus par le royaume de Nalvarune, à l'exception d'[[Elbor]] et Navæden.
    **Passage sous la régence de [[Theopanos Templaris]], de la [[coprincipauté d'Augolia]], qui revendique les anciens territoires de Navæden.
    *13 éposendre, 
    **Tenue du [[Sommet d'Elbor]] lors duquel la [[crise navalraise]] est en partie résolue entre les différents revendicants du territoire.
    **Proposition d'un dernier armistice par la couronne azurentoise, à nouveau refusée par [[Tajir Pa'an]].
    **Le [[royaume de Goast]] propose des pourparlers entre les deux parties impliquées dans la [[crise azurentoise]].
    **Proposition de création d'un tribunal gaiartois pour les futures crises.
    **Attentat destructeur à Issy qui « rédui[t] [le port] en ruines. »<ref>[[https://discord.com/channels/516302751500599316/1017475737852317768/1229550592670568559|Annonce officielle]] du même jour :« Le port d'Issy, symbole de notre prospérité et de notre connexion au monde, a été gravement endommagé. Une partie de ses installations a été réduite en ruines, provoquant un effondrement brutal et radical. Des vies innocentes ont été perdues, des familles ont été dévastées, et notre cité toute entière est plongée dans le deuil. »</ref>

    *16 éposendre, le [[duché de Dolivageä]] adopte par décret ''Louange du Duc'' comme son hymne officiel.
    *17 éposendre, propositions de revendications maritimes par [[Ruki tamashi|Ruki Tamashi]], rejetées par une partie des gaiartois<ref>[[https://discord.com/channels/516302751500599316/1017475737852317768/1230160196354052126|Annonce personnelle]] 5 réactions contre, 4 réactions pour</ref>.
    *24 éposendre, publication des revendications de la tribus des Templaris, sous l'égide de la [[principauté d'Augolia]].
    *25 éposendre, publication des revendications d'[[Elbor]].
    *26 éposendre, publication des revendications d'Industrial-Town
    *28 éposendre
    **Tajir Pa'an se rend aux armées royales d'Azurentos ;
    **Fondation de la Légion étrangère Gaiartoise par le roi [[Gaëtan Guillaume Garois|Gaëtan Garois]].

    <references />

    ```

    ```
    L''''an 2''' est une année primaire du Calendrier Gaiartois qui commence un dimanche. Elle fait suite à l'[[an 1]] et précède l'[[an 3]].

    Elle correspond à l'an 2001 du [[Calendrier Panimorphe]] et les mois de janvier à avril 2023 du [[Calendrier Minecraftien]].
    ==Événements==
    ===Gaiarkhè===

    * 3 gaiarkhè, [[Bleu Azure]] fonde [[la retraite du Démon]].
    * 4 gaiarkhè, [[Kætern d'Ange]] pille [[Frostbourne]] en profitant d'une manipulation de son maire.
    * 16 gaiarkhè
    ** [[Kætern d'Ange]] découvre la [[faille de Kætern]].
    ** [[Kætern d'Ange]] termine son voyage à travers [[Gaiartos]].
    ** [[Kætern d'Ange]] dévoile son premier tableau « [[:Fichier:Le voyage.png|Le Voyage]] ».
    * 18 gaiarkhè, [[Kætern d'Ange]] perd sa main à la bataille de [[Naxos|Naxos-Ouest et Naxos-Est]].
    * 21 gaiarkhè, [[Kætern d'Ange]] obtient sa [[première main en or]].

    ===Tempopidum===

    * 21 tempopidum, début des enchères de [[Kætern d'Ange]].
    * 22 tempopidum, fin des enchères de [[Kætern d'Ange]].

    ===Quinésil===

    * 5 quinésil, la fortune de [[Kætern d'Ange]] dépasse les 500 000[[Fichier:PieceBriocheItem.png|16x16px]].
    * 12 quinésil, naissance du [[Le Renard|Renard]].

    ===Éposendre===

    ```

    ```
    L''''an 1''' est une année tertiaire du Calendrier Gaiartois qui commence un jeudi. Elle fait suite au [[Ier siècle avant N.-C.|I<sup>er</sup> siècle avant N.C.]] et précède l'[[an 2]].

    Elle correspond à l'an 2000 du [[Calendrier Panimorphe]] et les mois de septembre à décembre 2022 du [[Calendrier Minecraftien]].

    == Événements ==

    === Gaiarkhè ===

    * 1 gaiarkhè, [[chute de la Panitropole]] au milieu des quatre continents de [[Gaiartos]].
    * 9 gaiarkhè, '''fin de l'[[Époque intermédiaire|Époque Intermédiaire]].'''
    * 10 gaiarkhè
    ** '''Début de l'[[Âge du Renouveau]].'''
    ** Début de la [[Nouvelle Colonisation]].
    ** Création du [[Calendrier Gaiartois]].
    ** [[Deltapythagore]] fonde [[Kappi|X-ray]] sur [[Bulfroï]].
    ** [[Osharia]] est pillée et incendiée par les habitants d'[[Kappi|X-ray]].
    ** [[Mazer O’Shaw|Mazer O'Shaw]] présente son idée de [[Ligue Gaiartoise]] dans une lettre ouverte.
    * 11 gaiarkhè
    ** [[Le Marchand]] fonde la [[tanière du Marchand]] sur [[Munakh]] a l'aide de sa fortune.
    ** [[Le Marchand]] approuve l'idée de [[Ligue Gaiartoise]] de [[Mazer O’Shaw|Mazer O'Shaw]] dans une lettre ouverte.
    ** [[Bossous]], [[Ludo]] et [[Mazer O’Shaw|Mazer O'Shaw]] fondent [[Midgard]] sur [[Damield]].
    * 12 gaiarkhè la [[première pièce baguette]] depuis la [[Nouvelle Colonisation]] est frappée pour X-ray.
    * 13 gaiarkhè
    ** La [[ferme d'Ange]] est pillée et incendiée par les colons d'[[Etherington]].
    ** [[Luïa d'Ange]], [[Oswald Quill]] et [[André d'Ange]] décèdent lors du pillage de la [[ferme d'Ange]].
    * 14 gaiarkhè
    ** [[Ptah]] fonde [[Ithil]] sur [[Damield]].
    ** La Ligue Gaiartoise est fondée par la signature des Accords de la Panitropole par [[Perimars]], [[Mazer O’Shaw|Mazer O'Shaw]], [[Ptah]], [[Bossous]], [[Le Marchand]] et [[Deltapythagore]].
    * 16 gaiarkhè
    ** [[Perimars]] et [[Dreeems]] fondent [[Brouswell]] sur [[Nettai]].
    ** La [[Panitropole]] reconnait [[Tharass]], ville de [[Damield]].
    ** [[Vincentuque]] fonde [[Cacahuète Empire]] sur [[Damield]].
    * 17 gaiarkhè
    ** [[Mazer O’Shaw|Mazer O'Shaw]] et [[Pryzri Yzip]] fondent [[Coprincipauté d'Hybloniopolis|Hybloniopolis]] sur [[Damield]].
    ** [[Cygale]] fonde [[Végétalia]] sur [[Damield]].
    ** [[Giga Zeus]] et [[Ze Atom]] fondent Gigatom qu'ils renomment ensuite [[Jorvik]] sur [[Riquez]].
    ** [[Pikachuz4]] fonde [[IndustrialTown]] sur [[Nettai]].
    * 19 gaiarkhè
    ** Un guerrier d'[[Kappi|X-ray]] tue un habitant de la [[tanière du Marchand]] lors d'un raid, [[Deltapythagore]] lance un ultimatum a la tanière dans la foulée, celui-ci est contesté par [[Coprincipauté d'Hybloniopolis|Hybloniopolis]], [[IndustrialTown]], [[Jorvik]] et la [[maison SangDragon]].
    ** [[Le Marchand]] rencontre [[Red69 Leaf|Red Iᵉʳ]] lors d'une rencontre diplomatique.
    ** La [[Panitropole]] reconnait [[Osharia]], ville de [[Munakh]].
    ** [[Lui]] renverse la [[Primatie|Primatie Issienne]] d'[[Hisenhorn]] et prend le pouvoir à [[Issy]], ville de [[Munakh]].
    * 20 gaiarkhè
    ** [[Drago SangDragon]] fonde le [[Royaume d'Alésia]].
    ** [[Kappi|X-ray]] attaque la [[tanière du Marchand]] lors de la [[Guerre des Deux-Heures]] et fini par défaire les défenses de la cité. [[Le Marchand]] et [[PainOraisins]] profitent de la défense pour faire évacuer les marchandises de la tanière qui se retrouve dissoute vers le [[Royaume d'Alésia]].
    ** [[AltarusS]] décède en combattant pour la [[tanière du Marchand]] pendant la [[Guerre des Deux-Heures]].
    ** [[Ludo]], habitant de la [[tanière du Marchand]], immigre vers [[Issy]].
    ** [[Hyelbi]], habitant de la [[tanière du Marchand]], immigre vers [[Brouswell]].
    ** La [[Ligue Gaiartoise]] exclut [[Kappi|X-ray]].
    * 22 gaiarkhè
    ** [[Drago SangDragon]] fonde [[GrainBeau]] sur [[Riquez]], elle devient la capitale du [[Royaume d'Alésia]].
    ** [[Le Marchand]] et [[PainOraisins]] fondent [[Port-Angéis]] sur des ruines sous la tutelle du Royaume d'Alésia.
    ** [[Cygale]] termine son exploration de [[Gaiartos]] et partage la [[Première carte de Gaiartos|première carte]] complète.
    * 23 gaiarkhè, [[Bobbyllettrer]] et plusieurs autres habitants de [[Brouswell]] quitte la ville avec une partie de ses ressources pour fonder [[Azuria]] sur [[Bulfroï]].
    * 24 gaiarkhè
    ** [[Maximus Maledicto]] fonde [[Frostbourne]] sur [[Riquez]].
    ** La première route inter ville depuis la [[Nouvelle Colonisation]] est érigée entre [[GrainBeau]] et [[Port-Angéis]] par le [[Royaume d'Alésia]].
    * 25 gaiarkhè, [[Jorvik]] quitte le [[Royaume d'Alésia]].
    * 27 gaiarkhè, la [[Panitropole]] reconnait [[Port-Angéis]], ville de [[Riquez]].
    * 29 gaiarkhè
    ** [[Oskey Ier]] fonde [[Etherington]] sur [[Damield]].
    ** [[Spipsycoteck]] fonde [[Issy|Fer-Rouge]] sur [[Nettai]].
    * 30 gaiarkhè
    ** [[Spipsycoteck]] fonde le [[Royaume de Fer-Rouge]] avec la [[Issy|ville éponyme]] comme capitale.
    ** [[Tortamor]] fonde [[Vicciopolis]] sur [[Nettai]].
    ** [[Végétalia]] rejoint le [[Royaume de Fer-Rouge]].

    === Tempopidum ===

    * 1ᵉʳ tempopidum
    ** La [[Panitropole]] reconnait la Ligue Gaiartois en tant qu'état.
    ** Les villes d'[[Etherington]] et [[Alster]] fondent le [[Royaume d'Hussey]].
    *2 tempopidum, [[XiloThor]] fonde [[Demacia]].
    *3 tempopidum, [[Fer-Rouge]] organise les premières enchères depuis la [[Nouvelle Colonisation]] avec les boites mystères.
    *6 tempopidum
    **Le [[Fer-Rouge|Royaume de Fer-Rouge]] et d'[[Royaume d'Hussey|Hussey]] signent le [[Pacte des Enfants de Gehenna]].
    **[[Absolon Enjouvar]] sous le nom de Snaurky infiltre et pille successivement les villes d'[[IndustrialTown]] et [[Brouswell]], ces pillages sont dénoncés a travers la communauté internationale.
    *7 tempopidum
    **Le [[Pacte des Enfants de Gehenna]] déclare [[Absolon Enjouvar]] hors-la-loi.
    **[[Winly]] fonde [[Naxos]].
    **[[Port-Angéis]] organise une fête pour inaugurer l'[[Hôtel de la ligue]] et l'[[Église de l'Ange-Pain]] et honorer le développement marchand de la ville et du reste du monde.
    *8 tempopidum
    **Le [[Royaume de Fer-Rouge]] annonce un ultimatum de 72h contre [[Issy]].
    **En réponse a l'ultimatum du [[Royaume de Fer-Rouge]], les villes d'[[Issy]], [[Azuria]] et [[Kappi|X-ray]] signent un accord de défense nommé [[IXA]].
    * 10 tempopidum, fin de la [[Nouvelle Colonisation]].
    * 11 tempopidum
    ** Le [[Pacte des Enfants de Gehenna]] déclare la guerre a [[Issy]] qui n'a pas répondu a l'ultimatum.
    ** Début de la [[Guerre de Gehenna]].
    *12 tempopidum
    **L'armée du [[Pacte des Enfants de Gehenna]] s'attaque a [[Issy]] et est repoussée par l'[[IXA]].
    **L'armée de l'[[IXA]] s'attaque a [[IndustrialTown]] et est repoussée par le [[Pacte des Enfants de Gehenna]].
    *13 tempopidum, [[FrostBourne]] fait sécession avec le [[Royaume d'Hussey]] pour se retirer de la [[Guerre de Gehenna]] et fonde le [[Frostbourne|Royaume de Frostbourne]].
    *15 tempopidum
    **L'armée de l'[[IXA]] s'attaque a [[Naxos]] et capture la ville défendue par le [[Pacte des Enfants de Gehenna]].
    **L'armée de l'[[IXA]] s'attaque a [[Alster]] et capture la ville défendue par le [[Pacte des Enfants de Gehenna]].
    *16 tempopidum, [[Incident Rubéonais]].

    === Quinésil ===

    === Éposendre ===

    * 15 éposendre, [[Kætern d'Ange]] trouve les objets volés par [[Absolon Enjouvar]] a [[Port-Angéis]].

    [[Catégorie:Gaiartos-Histoire]]

    ```
    Les mois incomplets ou vides le sont pas manque d'historiens (c'est en partie ça cause de ça que tu vas devoirs faire ce job).

    Voici maintenant en contexte les messages des 7 septs derniers jours. Ils ne sont là qu'en contexte, ne les résume pa,s mais tu peux t'en servir si besoin :
    #annonces :
    {messages_as_context_annonces}

    #géopolitique : 
    {messages_as_context_géopolitique}

    Voici maintenant les messages que tu vas devoirs résumés pour le format de fandom. ATTENTION, dans le résumé, je ne veux que les choses qui devraient être sur le fandom, donc n'éhsite pas à ne pas utiliser les messages peu importants, ou si rien ne s'est passé dans une journée, répond 'NONE' :
    #annonces :
    {messages_to_summarize_annonces}

    #géopolitique : 
    {messages_to_summarize_géopolitique}.

    Je veux que ta liste d'évènements soit sous le même format que le fandom, donc
    * jour mois
    **évènement1
    **évènement2
    **évènement ....

    S'il n'y a qu'un seul évènement, alors formatte le :
    * jour mois, évènement

    et s'il n'y a rien eu d'intéressant/important alors formatte le :
    * jour mois, NONE

    Voilà au boulot, dans ta réponse donne seulement ta réponse formattée sans commentaires additionnels.
    Je rappelle, ta réponse doit être en français, et résumer uniquement les jours à résumer, et pas ceux en contexte. Mais fait bien un résumé de TOUT. Je veux pas une réponse courte. je ne veux rien d'autres dans le message que ta réponse formattée. (pas de commentaires))
        """
        print(system_message)
        async with message.channel.typing():
            try:
                #dump system message to file
                with open("system_message.txt", "w", encoding="utf-8") as f:
                    f.write(system_message)
                response = generate_response("Procède.", system_message)
                print(response)
                if len(response) > 2000:
                    # send multiple messages in a row instead
                    for i in range(0, len(response), 2000):
                        await message.channel.send(response[i:i + 2000])
                else:
                    await message.channel.send(response)
            except Exception as e:
                await message.channel.send(f"Error: {e}")

    async def journal(self, message):
        # Define the list of channel IDs to process
        channel_ids = [718824042685136936, 1017475737852317768]  # Add your channel IDs here

        # Initialize dictionaries to store messages by channel name
        all_messages_to_summarize = {}
        all_messages_as_context = {}

        # For each channel
        for channel_id in channel_ids:
            # Fetch raw messages
            messages = await self.get_messages_since_last_x_hours(channel_id, context_hours)
            # Split messages into those to summarize and context messages
            messages_to_summarize, messages_as_context = await split_messages_by_hours(messages, hours_to_summarize)
            # Format messages after splitting
            messages_to_summarize_formatted = [await self.format_message(m) for m in messages_to_summarize]
            messages_as_context_formatted = [await self.format_message(m) for m in messages_as_context]

            # Get the channel name
            channel = self.get_channel(channel_id)
            channel_name = channel.name if channel else f"Channel {channel_id}"

            # Store the formatted messages in the dictionaries
            all_messages_to_summarize[channel_name] = messages_to_summarize_formatted
            all_messages_as_context[channel_name] = messages_as_context_formatted

        # Build the context messages string
        context_messages_str = ''
        for channel_name, messages in all_messages_as_context.items():
            context_messages_str += f"\n#{channel_name} :\n"
            context_messages_str += '\n'.join(messages)

        # Build the messages to summarize string
        messages_to_summarize_str = ''
        for channel_name, messages in all_messages_to_summarize.items():
            messages_to_summarize_str += f"\n#{channel_name} :\n"
            messages_to_summarize_str += '\n'.join(messages)
        system_message = f"""Tu seras un Agent dont le but est de résumé des évènements de salons RPs d'un salon discord dans un format tel que les résumés puissent être automatiquement ajoutés à une page fandom. Le serveur discord est le serveur discord d'un serveur minecraft nommé LaBoulangerie qui est un serveur géopolitique semi-rp. Tu résumeras le contenu du salon #géopolitique qui est le salon pour rp et faire de la géopolitique, mais tu résumeras aussi le salon #annonces qui est le salon des annocnes rp et géopolitiques, des villes, nations, entreprises, roganisations, joueurs etc... Tu seras donné la liste des messages des {hours_to_summarize} dernières heures à résumés. Chaque message aura son auteur, sa date, et son contenu textuel. Tu seras aussi donné en contexte, les messages des 7 précédents jours, mais eux ne seront pas à résumés, résume seulement ceux des {hours_to_summarize} (qui te seront donnés séparemment."
Le format d'un message sera 'author_name [date]: message_content' with [date] being in the format [An X, le DAY_NUMBER de CUSTOM_MONTH_NAME à TIME_IN_HOURS_MINUTES_SECONDS] parce que oui Gairtos utilise seulement 4 mois customs : Gaiarkhè, Tempopidum, Quinésil, Éposendre
Dans le Fandom, chaque An a sa propre page, et dedans à un moment il y a les évènements dans un ordre chronologique. Je vais te donner comme example le wikicode de la page de l'An 4 , regarde bien comment il est formatté. Tu devras seulement créer des tirets pour des évèhnements à des dates. Tu devras faire un tiret (et donc résumé) par jour donné, voici le wikicode complet de la page :
L''''an 4''' est une année tertiaire du Calendrier Gaiartois qui commence un vendredi. Elle fait suite à l'[[an 3]] et précède l'[[an 5]].

Elle correspond à l'an 2003 du [[Calendrier Panimorphe]] et les mois de septembre à décembre 2023 du [[Calendrier Minecraftien]].
```
==Événements==
===Gaiarkhè===

* 6 gaiarkhè, [[Kætern d'Ange]] fonde [[Dolivageä]].
* 9 gaiarkhè, [[Dolivageä]] adopte la [[:Fichier:Bannière de Dolivageä.png|Bannière de Dolivageä]].
* 10 gaiarkhè, [[Algard]] cède une partie de ses terres du nord à [[Dolivageä]] suite à un entretien entre [[Valgard Arkisson|Valgard Arkinsson]] et [[Kætern d'Ange]].
* 16 gaiarkhè
** [[Dolivageä]] adopte le [[:Fichier:Blason de Dolivageä.png|Blason de Dolivageä]].
** [[Dolivageä]] inaugure le [[Temple du Rubis]] et annonce sa participation au [[concours de patrimoine]] de la [[Panitropole]].
* 17 gaiarkhè
** [[Red 1er|Red Ier]] et [[Kætern d'Ange]] signent le [[Traité de Dolivageä]].
** [[Kætern d'Ange]] fonde le [[Duché de Dolivageä]] qui adopte la [[:Fichier:Bannière de Dolivageä.png|Bannière]] et le [[:Fichier:Blason de Dolivageä.png|Blason de Dolivageä]].
*21 gaiarkhè, le [[Duché de Dolivageä]] et sa [[Dolivageä|préfecture]] adoptent leur devise officielle « [[Nos louanges se chantent en Arthos]] ».
* 28 gaiarkhè, [[Dolivageä]] et [[Cushy]] inaugurent [[le Prismarin]].

===Tempopidum===

* 1ᵉʳ tempopidum
** [[PainOraisins]] décode l'énigme de [[Fryzhen]].
** [[Léonard Vizzini]] meurt dans un attentat commis, selon [[Goldcrest]], par des militants [[Familisme|familistes]].
** [[Adrian Hartmann]] publie l'essai [[Réflexion sur l'Illusion du Bien Commun]].
** Le [[Nalvarune|Royaume de Nalvarune]] adopte un régime oligarchique, [[Sir Matthew Percival Norrington|Matthew Norrington]], [[François LeNoble]] et [[Valérian "Caesar" Nerona|Valérian Nerona]] sont nommés [[Oligarque de Nalvarune|oligarques de Nalvarune]].
*3 tempopidum
**Le [[Petit Gaiartois]] publie le dixième numéro de [[Petit Gaiartois (journal)|son hebdomadaire]].
**[[Zagrivocha]] répond à l'annonce de l'assassinat de [[Léonard Vizzini]] en la remettant en cause et en condamnant l'attentat, et dénonce le traitement de l'affaire par le [[Petit Gaiartois]].
*5 tempopidum
**Le [[Petit Gaiartois]] répond à la réponse de [[Zagrivocha]] en la traitant comme une menace, annonce une édition spéciale sur les [[attentats des routes du Nether]] et lance un sondage sur l'augmentation du prix de [[Petit Gaiartois (journal)|son hebdomadaire]].
**[[Zagrivocha]] répond de nouveau au [[Petit Gaiartois]] en expliquant ne pas la menacer.
* 10 tempopidum, le [[Petit Gaiartois]] publie le onzième numéro de [[Petit Gaiartois (journal)|son hebdomadaire]].
* 11 tempopidum
** [[Marc Lèone]] fonde l'[[Île-Croissant Souveraine]] sur l'[[Île-Croissant|île éponyme]] ou s'installe la [[Congrégation de la Chape|Congrégation de la Chappe]] après avoir pillé une partie des ressources d'[[Annales d'Augolia|Augolia]].
** Le [[Parti Kæterniste]], dans le cadre de son combat contre le [[familisme]], publie l'[[affiche anti-familiste]] qu'elle fait mettre en vente à l'aide de la [[Fondation d'Ange]]. Il annonce travailler sur une proposition de premier [[Code Pénal du Royaume de Goast]], où serait interdit la « propagation des idées familistes ».
*12 tempopidum
**[[Kætern d'Ange]] lance le premier appel d'offre pour le chantier du [[Château de Dolivageä]].
**[[Ludovicus Ventor]] érige la route entre [[Cushy]] et [[Nalvarune]].
**[[Louis-Philippe Vizzini|Louis-Philippe Vizzini Iᵉʳ]] fonde le [[Parti Capitaliste Gaiartois]].
**[[Giga Zeus]] rend publique son usine à trident.
*13 tempopidum
**[[MMMOK]] pille [[Osharia]] puis rejoint [[Nalvarune]].
**[[Nalvarune]] adopte la [[Constitution de Nalvarune]].
**[[Louis-Philippe Vizzini|Louis-Philippe Vizzini Iᵉʳ]] annonce les avancées de l'enquête sur l'[[Assassinat de Léonard Vizzini]], les auteurs du meurtre semblent décédés et d'origines [[Annales d'Augolia|augoloises]].
*14 tempopidum
**[[MMMOK]] pille [[Nalvarune]] avant de se faire tuer par [[Lengevin]].
**[[Friolon|Friolon d'Orion]] organise la [[Congrégation des Marchands de Damield]] a [[Osterces]].
*15 tempopidum
**[[Kætern d'Ange]] trouve le cadavre de [[Tortamor]] et les [[journaux de Maximus]] après l'annonce de [[Cushy]]. Il y rencontre [[Maximus Maledictio]] et s'engage dans un combat avec, il finira par fuir avec les journaux en voyant la puissance de Maximus.
**[[Maximus Maledictio]] attaque les [[routes du Nether]] avec une armée de withers, il y rencontre [[Louis-Philippe Vizzini|Louis-Philippe Vizzini Iᵉʳ]] qu'il tue lors d'un combat.
**Un inconnu rase la fontaine du [[Cushy|quartier pauvre de Cushy]] lors d'une réunion au [[Panitropole|forum de la Panitropole]].
**[[Endafyr Quamat]] annonce le repos de [[Kætern d'Ange]] à [[Cushy]] suite à une blessure subie lors de son combat contre [[Maximus Maledictio]].
*16 tempopidum
**[[Louis-Philippe Vizzini 2ème|Louis-Philippe Vizzini II]] devient maire de [[Goldcrest]].
**Le [[Nalvarune|Royaume de Nalvarune]] modifie sa constitution pour y ajouter l'article concernant la Chancelière.
**[[Gabrielle de Marliave]] est nommée Chancelière du [[Nalvarune|Royaume de Nalvarune]] par les Oligarques.
**Le [[Nalvarune|Royaume de Nalvarune]] met en place sa vigilance attentat suite à l'[[attaque de Maximus Malédictio]].
*18 tempopidum, [[Maximus Maledictio|Maximus Malédictio]] fait quelques apparitions à [[Zagrivocha]] et [[Nalvarune]].
*20 tempopidum
**[[Adrian Hartmann]] annonce chercher un emplacement pour l'[[Université de Clover]].
**La [[Fondation d'Ange]] met en place le Fond Solimiste.
*23 tempopidum
**Osterces inaugure la Bibliothèque de la Congrégation de la Chape.
**[[Maximus Maledictio]] fait une apparition à [[Annales d'Augolia|Augolia]].
*24 tempopidum, le [[Petit Gaiartois]] publie le douzième numéro de [[Petit Gaiartois (journal)|son bihebdomadaire]].
*25 tempopidum
**Le [[Duché de Dolivageä]] inaugure le [[Pont Louis-Philippe Ier]] et la route entre [[Dolivageä]] et les [[ruines d'Asgardia]].
**[[Nalvarune]] entame des fouilles archéologiques à son lac.
**[[Valgard Arkisson|Valgard Arkinsson]] expose ses deux premières gravures a [[Algard]].
*27 tempopidum, [[Louis-Philippe Vizzini II]] fonde la [[Vizzini Print]].
*30 tempopidum [[Maximus Maledictio]] fait une apparition à [[Hernebhes des Solimes|Solimé]], par la suite, il tue [[Matzepol]], le meurtre est dénoncé par [[Nalvarune]] dans la foulée.
*31 tempopidum, [[Cushy]] met la tête de [[Maximus Maledictio]] à prix.
===Quinésil===

* 1er quinésil, [[Osterces]] inaugure la [[Tour d'Yggdrasil]].
* 2 quinésil, [[Osterces]] inaugure le [[café de l'Antique]].
* 3 quinésil, [[Osterces]] inaugure la route la reliant aux [[ruines d'Asgardia]].
* 4 quinésil
** [[Revax]] fonde le parti des [[Partageurs Gaiartois Unis]] et distribue des tracs exposant son programme et annonçant vouloir détruire les symboles du [[Royaume de Goast]] dont les routes, ce tract provoque une polémique au sein du Royaume.
** [[Dolivageä]] proclame hors-la-loi [[Revax]] et [[le Vagabond]] pour leur proximité avec l'idéologie [[Familisme|familiste]].
** La résidence [[Le Vagabond|du Vagabond]] a [[Solimé]] est perquisitionnée par les autorités goasts.
** [[Bidouille Dierne]] fonde la [[Bidouille Building Company]].
** La [[Société Vizzini]] organise une soirée d'inauguration pour son restaurant le [[Vizzini d'Or]].
** Le [[Nalvarune|Royaume de Nalvarune]] annonce avoir décodé les messages de [[Maximus Maledictio]].
** La résidence de [[Revax]] a [[Solimé]] est perquisitionnée par les autorités goasts.
*6 quinésil - [[Le Renard]] mène un coup d'état dans [[la retraite du Démon]] qu'il réussi et assassine [[Bleu Azure]].

===Éposendre===
```

Je le répète, toi devras juste ajouté des dates individuelles, et si besoin les évènements individuels. Car un résumé d'un jour peut avoir plusieurs choses (c'est même probable).
Le type d'évènement doit être un minimum important, comme tu le vois ici.
Voici d'autres examples de pages d'An pour que tu comprennes quels types d'évènements sont gardés :
```
L''''an 5''' est une année tertiaire du [[Calendrier Gaiartois]] qui commence un vendredi. Elle fait suite à l'[[an 4]] et précède l'[[an 6]].

Elle correspond à l'an 2004 du [[Calendrier Panimorphe]] et les mois de janvier à avril 2024 du [[Calendrier Minecraftien]].
==Événements==
===Gaiarkhè===

* 2 gaiarkè, le [[Shade]] annonce la tenue du duel entre lui-même et [[Louis-Philippe Vizzini 2ème|Louis-Philippe Vizzini II<sup>ème</sup>]].
*6 gaiarkhè
**[[Royaume de Goast|Goast]] rend son indépendance à [[Veltea]].
**[[Louis-Philippe Vizzini 2ème|Louis-Philippe Vizzini II<sup>ème</sup>]] bat le [[Shade]] en duel dans le cadre du [[Shade#Légende du Cristal (Depuis le 22 éposendre de l'an 4)|Défi du Shade]].
*7 gaiarkhè
**[[Veltea]] s'effondre et [[Algard]] en prend le contrôle créant une polémique.
**[[Végétalia]] s'effondre.
*8 gaiarkhè, [[Algard]] cède le contrôle de [[Veltea]].
*9 gaiarkhè
**[[Alster]] prend le contrôle de [[Veltea]].
**[[Kætern d'Ange]] annonce la tenue d'enchères au [[Château de Dolivageä]].

*14 gaiarkhè, création de la Fédération Familiste de Brulfroï après un rapprochement entre les deux pays de Kappi et de Zagrivocha.
*20 gaiarkhè
**Enchères à [[Dolivageä|Dolivagëa]]. Le [[royaume de Goast]] accuse [[Royaume de Nalvarune|Nalvarune]] d'avoir menti sur la rareté des dromadaires vendus ainsi que [[Vindicta]] d'avoir manipulé les prix en surenchérissant les lots<ref>[[https://discord.com/channels/516302751500599316/1017475737852317768/1198681122247286804|Annonce officielle du 21 janvier]]</ref>.
**[[Ormick Ier|Ormick I<sup>er</sup>]] prend le trône vacant à [[Vicciopolis]] et dans la [[coprincipauté d'Hybloniopolis]], confirmant l'union personnelle entre les deux cité-États.

* 24 gaiarkhè, érection d'une première Grande Tour Magique de Gaiartos, l'Aegeria, à Osterces.

*26 gaiarkhè, inauguration de la bibliothèque à [[Cushy]].

===Tempopidum===

*3 tempopidum, [[Jorvik]] (aujourd'hui Poséage) rejoint le [[royaume de Goast]] pour la commémoration des 1 an de la fin de la [[Guerre des Quatre Armées]] dans le musée de [[Tharass]].
*11 gaiarkhè
**Début de la publication posthume de l'œuvre ''De la démocratie en Gaiartos'' de [[Mazer O’Shaw|Mazer O'Shaw]].
**Friolon II prend la relève après que le précédent souverain d'[[Osterces]] ait été tué dans des « circonstances douteuses »<ref>[[https://discord.com/channels/516302751500599316/1017475737852317768/1206304677335924776|Annonce de la ville d'Osterces]] du même jour :« C'est depuis Osterces, que je vous parle : moi, Friolon deuxième du nom, prend la relève de la direction de la ville. En effet, notre précédent souverain et fondateur est décédé en de douteuses circonstances.  » </ref>.

*12 gaiarkhè, le [[Azurentos|duché d'Azurentos]] déclare son indépendance du [[royaume de Nalvarune]], créant le [[royaume d'Astréa]], qui provoque une crise interne à Nalvarune.
*17 gaiarkhè, organisation du concours quadriennal de course des bateaux de glace dans la [[Fédération Familiste de Bulfroi|F.F.B.]]
*21 gaiarkhè, pousse de l'« Arbre de vie » à Algard sur lequel le Jarl a étendu sa résidence afin d'en apprendre davantage<ref>[[https://discord.com/channels/516302751500599316/1017475737852317768/1209967995649007656|Annonce de la ville d'Algard]] du même jour</ref>.
*23 tempopidum, mariage entre [[Ormick Ier|Ormick I<sup>er</sup>]] et [[Louis-Philippe Vizzini 2ème|Louis-Philippe Vizzini II<sup>ème</sup>]] à [[Vicciopolis]].
*21 tempopidum, ouverture des candidatures pour l'élection des Grands Jurés du Comité des Brasseurs afin de revitaliser l'organisation<ref>[[https://discord.com/channels/516302751500599316/1017475737852317768/1210219857090576437|Annonce du Comité]] le jour même</ref>.
*25 tempodidum, fondation du [[royaume de Crusentia]] avec le maire d'[[Osharia]], les titulaires des trônes d'[[Coprincipauté d'Hybloniopolis|Hybloniopolis]] et de [[Vicciopolis]] et le maire de la cité-État de [[Cushy]].
*25 tempopidum, naissance des enfants de [[Ormick Ier|Ormick I<sup>er</sup>]] et [[Louis-Philippe Vizzini 2ème|Louis-Philippe Vizzini II<sup>ème</sup>]] : Louis-Philippe Vizzini O'Shaw I<sup>er</sup> ''Junior'' et Emarant Vizzini O'Shaw I<sup>er</sup> ''Junior''
*28 tempopidum
**Aésultats des élections au [[Comité des Brasseurs]] : [[Nicolas Junlase]], [[Ruki tamashi|Ruki Tamashi]] et [[Ormick Ier|Ormick I<sup>er</sup>]] deviennent Grands Jurés.
**Abdication du [[Guillaume Verentti Garois|Guillaume Garois I<sup>er</sup>]] en faveur de son fils [[Gaëtan Guillaume Garois|Gaëtan Garois II]] qui monte sur le trône à [[Astréa]].

===Quinésil===

*2 quinésil, nouvelles attaques sur les routes nétheresques.
*3 quinésil
**Mort de [[Nicolas Junlase]].
**Disparition de ReNouy, voleur connu.

*4 quinésil, 
**Azurentos commercialise de la vodka black et du vin lumineux, vente condamnée par le Comité des Brasseurs qui fait proposer la guerre contre Azurentos au Conseil Constitutionnel de Goast.<ref>https://discord.com/channels/516302751500599316/718824042685136936/1214185513477480468</ref>
**Création [[Rassemblement des Saveurs Brassicole]] par le roi [[Gaëtan Guillaume Garois|Gaëtan Garois II]] en réponse à « [l'impossibilité] d'exploiter [ces] boisson[s] à moins d'en être le breveté »<ref>[[https://discord.com/channels/516302751500599316/1017475737852317768/1214009565323198484|Annonce officielle de l'organisation]]</ref>.
*6 quinésil, création de la [[guilde des Marchands]] par [[Louis-Philippe Vizzini 2ème|Louis-Philippe Vizzini II<sup>ème</sup>]].
*13 quinésil, annonce d'une collaboration entre le [[royaume de Goast]] et la [[Fédération Familiste de Bulfroi|F.F.B.]] pour la surveillance de l'exploitation des glaciers du nord, ainsi qu'une collaboration entre ce même royaume et la [[principauté d'Augolia]] pour revégétaliser et protéger l’environnement des [[Iles-de-Fer]].
*17 quinésil, tenue d'enchères pour l'inauguration du château de [[Tharass]].
*24 quinésil
**Effondrement de la ville du [[royaume de Nalvarune]] suite aux problèmes internes due aux sécessionnistes d'Azurentos.
**La famille royale excepté le roi [[Gaëtan Guillaume Garois|Gaëtan Garois II]] se retire pour construire une villégiature près de [[Nalvarune]] afin de protéger les ruines de la ville.
*29 quinésil
**Début de construction d'un quartier résidentiel à [[Osterces]].
**Signature du [[traité de Vicciopolis]] pour le libre échange entre le [[royaume de Goast]] et le [[royaume de Crusentia]].

===Éposendre===

*1<sup>er</sup> éposendre
**Mort du roi [[Gaëtan Guillaume Garois|Guillaume Garois I<sup>er</sup>]] et explications de la nouvelle constitution du [[royaume d'Astréa]] avec un pouvoir monarchique absolu et un Sénat consultatif, ainsi que présentation du culte astréen.
**Canulars du 1<sup>er</sup> avril.
**Mariage de [[Red 1er|Red I<sup>er</sup>]] et [[Friolon|Magelion d'Orion II]] lors duquel l'ex-roi décède accidentellement. Création d'une journée nationale en [[Royaume de Goast|Goast]] et vague de soutiens internationaux lors de son annonce le 3 éposendre.
**Effondrement de [[Midgard]], qui est pillée par Algard puis les ressources de laquelle son rendue à son nouveau suzerain : [[Coprincipauté d'Hybloniopolis|Hybloniopolis]].

*2 éposendre, [[Tajir Pa'an]] déclare la [[Commune d'Azurentos]] tandis que la famille royale s'est absentée, commençant la [[crise azurentoise]].
*3 éposendre, création de la Légion étrangère gaiartoise par le roi [[Gaëtan Guillaume Garois|Gaëtan Garois II]]
*4 éposendre, érection d'une statue en l'honneur du défunt Red I<sup>er</sup>.
*5 éposendre
**La couronne azurentoise déclare l'État d'urgence et la répression anti-insurrection.
**Annonce des échecs des pourparlers sous l'égide d'[[Industrial-Town]] entre les deux parties impliquées à cause du refus de la couronne azurentoise.

*6 éposendre, 
**La Panitropole appelle les gaiartois à l'aider pour construire un nouveau port, l'[[évent du port]].
**Propositions de pourparlers par la couronne azurentoise, refusée par [[Tajir Pa'an]].

*10 éposendre,
**Proposition de création de l'''Indestructi'Banque'' par [[Friolon|Magelion d'Orion II]].
**Cushy déclare revendiquer la presque intégralité des territoires anciennement détenus par le royaume de Nalvarune, à l'exception d'[[Elbor]] et Navæden.
**Passage sous la régence de [[Theopanos Templaris]], de la [[coprincipauté d'Augolia]], qui revendique les anciens territoires de Navæden.
*13 éposendre, 
**Tenue du [[Sommet d'Elbor]] lors duquel la [[crise navalraise]] est en partie résolue entre les différents revendicants du territoire.
**Proposition d'un dernier armistice par la couronne azurentoise, à nouveau refusée par [[Tajir Pa'an]].
**Le [[royaume de Goast]] propose des pourparlers entre les deux parties impliquées dans la [[crise azurentoise]].
**Proposition de création d'un tribunal gaiartois pour les futures crises.
**Attentat destructeur à Issy qui « rédui[t] [le port] en ruines. »<ref>[[https://discord.com/channels/516302751500599316/1017475737852317768/1229550592670568559|Annonce officielle]] du même jour :« Le port d'Issy, symbole de notre prospérité et de notre connexion au monde, a été gravement endommagé. Une partie de ses installations a été réduite en ruines, provoquant un effondrement brutal et radical. Des vies innocentes ont été perdues, des familles ont été dévastées, et notre cité toute entière est plongée dans le deuil. »</ref>

*16 éposendre, le [[duché de Dolivageä]] adopte par décret ''Louange du Duc'' comme son hymne officiel.
*17 éposendre, propositions de revendications maritimes par [[Ruki tamashi|Ruki Tamashi]], rejetées par une partie des gaiartois<ref>[[https://discord.com/channels/516302751500599316/1017475737852317768/1230160196354052126|Annonce personnelle]] 5 réactions contre, 4 réactions pour</ref>.
*24 éposendre, publication des revendications de la tribus des Templaris, sous l'égide de la [[principauté d'Augolia]].
*25 éposendre, publication des revendications d'[[Elbor]].
*26 éposendre, publication des revendications d'Industrial-Town
*28 éposendre
**Tajir Pa'an se rend aux armées royales d'Azurentos ;
**Fondation de la Légion étrangère Gaiartoise par le roi [[Gaëtan Guillaume Garois|Gaëtan Garois]].

<references />

```

```
L''''an 2''' est une année primaire du Calendrier Gaiartois qui commence un dimanche. Elle fait suite à l'[[an 1]] et précède l'[[an 3]].

Elle correspond à l'an 2001 du [[Calendrier Panimorphe]] et les mois de janvier à avril 2023 du [[Calendrier Minecraftien]].
==Événements==
===Gaiarkhè===

* 3 gaiarkhè, [[Bleu Azure]] fonde [[la retraite du Démon]].
* 4 gaiarkhè, [[Kætern d'Ange]] pille [[Frostbourne]] en profitant d'une manipulation de son maire.
* 16 gaiarkhè
** [[Kætern d'Ange]] découvre la [[faille de Kætern]].
** [[Kætern d'Ange]] termine son voyage à travers [[Gaiartos]].
** [[Kætern d'Ange]] dévoile son premier tableau « [[:Fichier:Le voyage.png|Le Voyage]] ».
* 18 gaiarkhè, [[Kætern d'Ange]] perd sa main à la bataille de [[Naxos|Naxos-Ouest et Naxos-Est]].
* 21 gaiarkhè, [[Kætern d'Ange]] obtient sa [[première main en or]].

===Tempopidum===

* 21 tempopidum, début des enchères de [[Kætern d'Ange]].
* 22 tempopidum, fin des enchères de [[Kætern d'Ange]].

===Quinésil===

* 5 quinésil, la fortune de [[Kætern d'Ange]] dépasse les 500 000[[Fichier:PieceBriocheItem.png|16x16px]].
* 12 quinésil, naissance du [[Le Renard|Renard]].

===Éposendre===

```

```
L''''an 1''' est une année tertiaire du Calendrier Gaiartois qui commence un jeudi. Elle fait suite au [[Ier siècle avant N.-C.|I<sup>er</sup> siècle avant N.C.]] et précède l'[[an 2]].

Elle correspond à l'an 2000 du [[Calendrier Panimorphe]] et les mois de septembre à décembre 2022 du [[Calendrier Minecraftien]].

== Événements ==

=== Gaiarkhè ===

* 1 gaiarkhè, [[chute de la Panitropole]] au milieu des quatre continents de [[Gaiartos]].
* 9 gaiarkhè, '''fin de l'[[Époque intermédiaire|Époque Intermédiaire]].'''
* 10 gaiarkhè
** '''Début de l'[[Âge du Renouveau]].'''
** Début de la [[Nouvelle Colonisation]].
** Création du [[Calendrier Gaiartois]].
** [[Deltapythagore]] fonde [[Kappi|X-ray]] sur [[Bulfroï]].
** [[Osharia]] est pillée et incendiée par les habitants d'[[Kappi|X-ray]].
** [[Mazer O’Shaw|Mazer O'Shaw]] présente son idée de [[Ligue Gaiartoise]] dans une lettre ouverte.
* 11 gaiarkhè
** [[Le Marchand]] fonde la [[tanière du Marchand]] sur [[Munakh]] a l'aide de sa fortune.
** [[Le Marchand]] approuve l'idée de [[Ligue Gaiartoise]] de [[Mazer O’Shaw|Mazer O'Shaw]] dans une lettre ouverte.
** [[Bossous]], [[Ludo]] et [[Mazer O’Shaw|Mazer O'Shaw]] fondent [[Midgard]] sur [[Damield]].
* 12 gaiarkhè la [[première pièce baguette]] depuis la [[Nouvelle Colonisation]] est frappée pour X-ray.
* 13 gaiarkhè
** La [[ferme d'Ange]] est pillée et incendiée par les colons d'[[Etherington]].
** [[Luïa d'Ange]], [[Oswald Quill]] et [[André d'Ange]] décèdent lors du pillage de la [[ferme d'Ange]].
* 14 gaiarkhè
** [[Ptah]] fonde [[Ithil]] sur [[Damield]].
** La Ligue Gaiartoise est fondée par la signature des Accords de la Panitropole par [[Perimars]], [[Mazer O’Shaw|Mazer O'Shaw]], [[Ptah]], [[Bossous]], [[Le Marchand]] et [[Deltapythagore]].
* 16 gaiarkhè
** [[Perimars]] et [[Dreeems]] fondent [[Brouswell]] sur [[Nettai]].
** La [[Panitropole]] reconnait [[Tharass]], ville de [[Damield]].
** [[Vincentuque]] fonde [[Cacahuète Empire]] sur [[Damield]].
* 17 gaiarkhè
** [[Mazer O’Shaw|Mazer O'Shaw]] et [[Pryzri Yzip]] fondent [[Coprincipauté d'Hybloniopolis|Hybloniopolis]] sur [[Damield]].
** [[Cygale]] fonde [[Végétalia]] sur [[Damield]].
** [[Giga Zeus]] et [[Ze Atom]] fondent Gigatom qu'ils renomment ensuite [[Jorvik]] sur [[Riquez]].
** [[Pikachuz4]] fonde [[IndustrialTown]] sur [[Nettai]].
* 19 gaiarkhè
** Un guerrier d'[[Kappi|X-ray]] tue un habitant de la [[tanière du Marchand]] lors d'un raid, [[Deltapythagore]] lance un ultimatum a la tanière dans la foulée, celui-ci est contesté par [[Coprincipauté d'Hybloniopolis|Hybloniopolis]], [[IndustrialTown]], [[Jorvik]] et la [[maison SangDragon]].
** [[Le Marchand]] rencontre [[Red69 Leaf|Red Iᵉʳ]] lors d'une rencontre diplomatique.
** La [[Panitropole]] reconnait [[Osharia]], ville de [[Munakh]].
** [[Lui]] renverse la [[Primatie|Primatie Issienne]] d'[[Hisenhorn]] et prend le pouvoir à [[Issy]], ville de [[Munakh]].
* 20 gaiarkhè
** [[Drago SangDragon]] fonde le [[Royaume d'Alésia]].
** [[Kappi|X-ray]] attaque la [[tanière du Marchand]] lors de la [[Guerre des Deux-Heures]] et fini par défaire les défenses de la cité. [[Le Marchand]] et [[PainOraisins]] profitent de la défense pour faire évacuer les marchandises de la tanière qui se retrouve dissoute vers le [[Royaume d'Alésia]].
** [[AltarusS]] décède en combattant pour la [[tanière du Marchand]] pendant la [[Guerre des Deux-Heures]].
** [[Ludo]], habitant de la [[tanière du Marchand]], immigre vers [[Issy]].
** [[Hyelbi]], habitant de la [[tanière du Marchand]], immigre vers [[Brouswell]].
** La [[Ligue Gaiartoise]] exclut [[Kappi|X-ray]].
* 22 gaiarkhè
** [[Drago SangDragon]] fonde [[GrainBeau]] sur [[Riquez]], elle devient la capitale du [[Royaume d'Alésia]].
** [[Le Marchand]] et [[PainOraisins]] fondent [[Port-Angéis]] sur des ruines sous la tutelle du Royaume d'Alésia.
** [[Cygale]] termine son exploration de [[Gaiartos]] et partage la [[Première carte de Gaiartos|première carte]] complète.
* 23 gaiarkhè, [[Bobbyllettrer]] et plusieurs autres habitants de [[Brouswell]] quitte la ville avec une partie de ses ressources pour fonder [[Azuria]] sur [[Bulfroï]].
* 24 gaiarkhè
** [[Maximus Maledicto]] fonde [[Frostbourne]] sur [[Riquez]].
** La première route inter ville depuis la [[Nouvelle Colonisation]] est érigée entre [[GrainBeau]] et [[Port-Angéis]] par le [[Royaume d'Alésia]].
* 25 gaiarkhè, [[Jorvik]] quitte le [[Royaume d'Alésia]].
* 27 gaiarkhè, la [[Panitropole]] reconnait [[Port-Angéis]], ville de [[Riquez]].
* 29 gaiarkhè
** [[Oskey Ier]] fonde [[Etherington]] sur [[Damield]].
** [[Spipsycoteck]] fonde [[Issy|Fer-Rouge]] sur [[Nettai]].
* 30 gaiarkhè
** [[Spipsycoteck]] fonde le [[Royaume de Fer-Rouge]] avec la [[Issy|ville éponyme]] comme capitale.
** [[Tortamor]] fonde [[Vicciopolis]] sur [[Nettai]].
** [[Végétalia]] rejoint le [[Royaume de Fer-Rouge]].

=== Tempopidum ===

* 1ᵉʳ tempopidum
** La [[Panitropole]] reconnait la Ligue Gaiartois en tant qu'état.
** Les villes d'[[Etherington]] et [[Alster]] fondent le [[Royaume d'Hussey]].
*2 tempopidum, [[XiloThor]] fonde [[Demacia]].
*3 tempopidum, [[Fer-Rouge]] organise les premières enchères depuis la [[Nouvelle Colonisation]] avec les boites mystères.
*6 tempopidum
**Le [[Fer-Rouge|Royaume de Fer-Rouge]] et d'[[Royaume d'Hussey|Hussey]] signent le [[Pacte des Enfants de Gehenna]].
**[[Absolon Enjouvar]] sous le nom de Snaurky infiltre et pille successivement les villes d'[[IndustrialTown]] et [[Brouswell]], ces pillages sont dénoncés a travers la communauté internationale.
*7 tempopidum
**Le [[Pacte des Enfants de Gehenna]] déclare [[Absolon Enjouvar]] hors-la-loi.
**[[Winly]] fonde [[Naxos]].
**[[Port-Angéis]] organise une fête pour inaugurer l'[[Hôtel de la ligue]] et l'[[Église de l'Ange-Pain]] et honorer le développement marchand de la ville et du reste du monde.
*8 tempopidum
**Le [[Royaume de Fer-Rouge]] annonce un ultimatum de 72h contre [[Issy]].
**En réponse a l'ultimatum du [[Royaume de Fer-Rouge]], les villes d'[[Issy]], [[Azuria]] et [[Kappi|X-ray]] signent un accord de défense nommé [[IXA]].
* 10 tempopidum, fin de la [[Nouvelle Colonisation]].
* 11 tempopidum
** Le [[Pacte des Enfants de Gehenna]] déclare la guerre a [[Issy]] qui n'a pas répondu a l'ultimatum.
** Début de la [[Guerre de Gehenna]].
*12 tempopidum
**L'armée du [[Pacte des Enfants de Gehenna]] s'attaque a [[Issy]] et est repoussée par l'[[IXA]].
**L'armée de l'[[IXA]] s'attaque a [[IndustrialTown]] et est repoussée par le [[Pacte des Enfants de Gehenna]].
*13 tempopidum, [[FrostBourne]] fait sécession avec le [[Royaume d'Hussey]] pour se retirer de la [[Guerre de Gehenna]] et fonde le [[Frostbourne|Royaume de Frostbourne]].
*15 tempopidum
**L'armée de l'[[IXA]] s'attaque a [[Naxos]] et capture la ville défendue par le [[Pacte des Enfants de Gehenna]].
**L'armée de l'[[IXA]] s'attaque a [[Alster]] et capture la ville défendue par le [[Pacte des Enfants de Gehenna]].
*16 tempopidum, [[Incident Rubéonais]].

=== Quinésil ===

=== Éposendre ===

* 15 éposendre, [[Kætern d'Ange]] trouve les objets volés par [[Absolon Enjouvar]] a [[Port-Angéis]].

[[Catégorie:Gaiartos-Histoire]]

```
Les mois incomplets ou vides le sont pas manque d'historiens (c'est en partie ça cause de ça que tu vas devoirs faire ce job).

Voici maintenant en contexte les messages des 7 derniers jours. Ils ne sont là qu'en contexte, ne les résume pas, mais tu peux t'en servir si besoin :{context_messages_str}

Voici maintenant les messages que tu vas devoir résumer pour le format de Fandom. ATTENTION, dans le résumé, je ne veux que les choses qui devraient être sur le Fandom, donc n'hésite pas à ne pas utiliser les messages peu importants, ou si rien ne s'est passé dans une journée, répond 'NONE' :{messages_to_summarize_str}


Je veux que ta liste d'évènements soit sous le même format que le fandom, donc
* jour mois
**évènement1
**évènement2
**évènement ....

S'il n'y a qu'un seul évènement, alors formatte le :
* jour mois, évènement

et s'il n'y a rien eu d'intéressant/important alors formatte le :
* jour mois, NONE

Voilà au boulot, dans ta réponse donne seulement ta réponse formattée sans commentaires additionnels.
Je rappelle, ta réponse doit être en français, et résumer uniquement les jours à résumer, et pas ceux en contexte.

En fait oublie la réponse pour le fandom, rédige à la place ta réponse à la manière d'un présentateur télé un journal à propos du contenu à résumer, qui présenterait ce qu'il s'est passé dans gaiartos ces derniers temps.
Voilà une aide pour la forme et le style d'un journal :






1. **Ouverture et Salutation**
   - **Phrase d'accroche** : Commencer par une phrase impactante pour capter l'attention.
   - **Présentation** : Salutation chaleureuse et présentation du présentateur.
   - **Annonce générale** : Brève mention des événements ou thèmes qui seront abordés.

2. **Développement des Nouvelles**
   - **Hiérarchisation** : Présenter les informations en commençant par les plus importantes.
   - **Style narratif** : Utiliser un ton clair, professionnel et engageant.
   - **Transitions fluides** : Passer d'un sujet à l'autre en douceur, avec des phrases de liaison.
   - **Éviter les répétitions** : Varier le vocabulaire et les structures de phrases.
   - **Emphase sur les faits** : Prioriser l'objectivité, en mettant en avant les faits saillants.
   - **Interactions** : Si approprié, inclure des questions rhétoriques pour impliquer le public.

3. **Conclusion**
   - **Résumé rapide** : Rappeler les points clés abordés sans entrer dans les détails.
   - **Note finale** : Terminer sur une pensée positive, une citation inspirante, ou une perspective pour l'avenir.
   - **Au revoir** : Remercier les téléspectateurs et les inviter à la prochaine édition.

---

**Conseils pour le Style du Présentateur :**

- **Ton et Langage**
  - Utiliser un langage accessible mais professionnel.
  - Maintenir un rythme de parole modéré pour assurer la compréhension.
  - Employer des tournures de phrases actives pour dynamiser le discours.

- **Engagement du Public**
  - Adresser directement les téléspectateurs avec des "vous".
  - Poser des questions ou utiliser des exclamations pour maintenir l'attention.

- **Expressions et Intonation**
  - Varier l'intonation pour souligner l'importance des informations.
  - Utiliser des expressions faciales et gestuelles (si visuel) pour renforcer le message.

- **Flexibilité**
  - Adapter la longueur et la profondeur des segments en fonction du nombre et de l'importance des événements.
  - Être prêt à modifier l'ordre des informations si nécessaire pour une meilleure cohérence.

- **Neutralité et Objectivité**
  - Présenter les informations de manière impartiale.
  - Éviter les jugements de valeur ou les biais personnels.

Voilà à toi de jouer monsieur le présentateur.
"""
        print(system_message)
        async with message.channel.typing():
            try:
                response = generate_response("Procède.", system_message)
                print(response)
                if len(response) > 2000:
                    # send multiple messages in a row instead
                    for i in range(0, len(response), 2000):
                        await message.channel.send(response[i:i + 2000])
                else:
                    await message.channel.send(response)
            except Exception as e:
                await message.channel.send(f"Error: {e}")


client = MyClient()

# Run the client using the token
client.run(TOKEN)  # bot=False means it runs as a user account
