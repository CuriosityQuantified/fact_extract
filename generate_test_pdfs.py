#!/usr/bin/env python3
"""
Script to generate 10 test PDF files with varying content for fact extraction testing.
Each PDF will have between 500-5000 words on different topics.
"""

import os
import random
from fpdf import FPDF
import textwrap

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

# Sample topics with content
TOPICS = {
    "artificial_intelligence": """
    Artificial intelligence (AI) is intelligence demonstrated by machines, as opposed to intelligence of humans and other animals. Example tasks in which this is done include speech recognition, computer vision, translation between (natural) languages, as well as other mappings of inputs.
    
    AI applications include advanced web search engines (such as Google), recommendation systems (used by YouTube, Amazon, and Netflix), understanding human speech (such as Siri and Alexa), self-driving cars (such as Tesla), generative or creative tools (ChatGPT and AI art), automated decision-making, and competing at the highest level in strategic game systems (such as chess and Go).
    
    As machines become increasingly capable, tasks considered to require "intelligence" are often removed from the definition of AI, a phenomenon known as the AI effect. For instance, optical character recognition is frequently excluded from things considered to be AI, having become a routine technology.
    
    Artificial intelligence was founded as an academic discipline in 1956, and in the years since it has experienced several waves of optimism, followed by disappointment and the loss of funding (known as an "AI winter"), followed by new approaches, success, and renewed funding. AI research has tried and discarded many different approaches, including simulating the brain, modeling human problem solving, formal logic, large databases of knowledge, and imitating animal behavior. In the first decades of the 21st century, highly mathematical and statistical machine learning has dominated the field, and this technique has proved highly successful, helping to solve many challenging problems throughout industry and academia.
    
    The various sub-fields of AI research are centered around particular goals and the use of particular tools. The traditional goals of AI research include reasoning, knowledge representation, planning, learning, natural language processing, perception, and the ability to move and manipulate objects. General intelligence (the ability to solve an arbitrary problem) is among the field's long-term goals. To solve these problems, AI researchers have adapted and integrated a wide range of problem-solving techniques, including search and mathematical optimization, formal logic, artificial neural networks, and methods based on statistics, probability, and economics. AI also draws upon computer science, psychology, linguistics, philosophy, and many other fields.
    """,
    
    "climate_change": """
    Climate change refers to long-term shifts in temperatures and weather patterns. These shifts may be natural, such as through variations in the solar cycle. But since the 1800s, human activities have been the main driver of climate change, primarily due to burning fossil fuels like coal, oil and gas.
    
    Burning fossil fuels generates greenhouse gas emissions that act like a blanket wrapped around the Earth, trapping the sun's heat and raising temperatures. Examples of greenhouse gas emissions that are causing climate change include carbon dioxide and methane. These come from using gasoline for driving a car or coal for heating a building, for example. Clearing land and forests can also release carbon dioxide. Landfills for garbage are a major source of methane emissions. Energy, industry, transport, buildings, agriculture and land use are among the main emitters.
    
    Greenhouse gas concentrations are at their highest levels in 2 million years and continue to rise. As a result, the Earth is now about 1.1°C warmer than it was in the 1800s. The last decade (2011-2020) was the warmest on record.
    
    Many people think climate change mainly means warmer temperatures. But temperature rise is only the beginning of the story. Because the Earth is a system, where everything is connected, changes in one area can influence changes in all others. The consequences of climate change now include, among others, intense droughts, water scarcity, severe fires, rising sea levels, flooding, melting polar ice, catastrophic storms and declining biodiversity.
    
    People are experiencing climate change in diverse ways. Climate change can affect our health, ability to grow food, housing, safety and work. Some of us are already more vulnerable to climate impacts, such as people living in small island developing states and other developing countries. Conditions like sea-level rise and saltwater intrusion have advanced to the point where whole communities have had to relocate, and protracted droughts are putting people at risk of famine. In the future, the number of "climate refugees" is expected to rise.
    """,
    
    "renewable_energy": """
    Renewable energy is energy derived from natural sources that are replenished at a higher rate than they are consumed. Sunlight and wind, for example, are such sources that are constantly being replenished. Renewable energy sources are plentiful and all around us.
    
    Fossil fuels - coal, oil and gas - on the other hand, are non-renewable resources that take hundreds of millions of years to form. Fossil fuels, when burned to produce energy, cause harmful greenhouse gas emissions, such as carbon dioxide.
    
    Renewable energy, on the other hand, typically produces much lower emissions than fossil fuels and often zero. By 2050, almost 90% of electricity could be provided by renewable energy. The most common renewable energy sources are:
    
    Solar energy from the sun has been harnessed by humans since ancient times using a range of ever-evolving technologies. Solar energy technologies include solar heat, solar photovoltaics, solar thermal electricity and solar architecture, which can make considerable contributions to solving some of the most urgent energy problems the world now faces.
    
    Wind power harnesses the kinetic energy of moving air by using large wind turbines located on land or in sea or freshwater. Wind energy has been used for millennia, but is now being adapted to modern electricity generation.
    
    Hydropower harnesses the energy of moving water, which can then be used to generate electricity. Hydropower is the largest single renewable energy source today, providing around 16% of the world's electricity.
    
    Geothermal energy uses the accessible thermal energy from the Earth's interior. Heat is extracted from geothermal reservoirs using wells or other means. Reservoirs that are naturally sufficiently hot and permeable are called hydrothermal reservoirs, whereas reservoirs that are sufficiently hot but that are improved with hydraulic stimulation are called enhanced geothermal systems.
    
    Bioenergy is a form of renewable energy derived from biomass to generate electricity and heat or to produce liquid fuels for transport. Biomass is any organic matter that has stored sunlight in the form of chemical energy. It can be used directly as a fuel or processed into liquids or gases.
    """,
    
    "quantum_computing": """
    Quantum computing is a type of computation that harnesses the collective properties of quantum states, such as superposition, interference, and entanglement, to perform calculations. The devices that perform quantum computations are known as quantum computers. Though current quantum computers are too small to outperform usual (classical) computers for practical applications, they are believed to be capable of solving certain computational problems, such as integer factorization (which underlies RSA encryption), substantially faster than classical computers. The study of quantum computing is a subfield of quantum information science.
    
    Quantum computing began in the early 1980s, when physicist Paul Benioff proposed a quantum mechanical model of the Turing machine. Richard Feynman and Yuri Manin later suggested that a quantum computer had the potential to simulate things that a classical computer could not. In 1994, Peter Shor developed a quantum algorithm for factoring integers that has the potential to decrypt RSA-encrypted communications. Despite ongoing experimental progress since the late 1990s, most researchers believe that "fault-tolerant quantum computing still a rather distant dream". In recent years, investment in quantum computing research has increased in the public and private sectors. On 23 October 2019, Google AI, in partnership with the U.S. National Aeronautics and Space Administration (NASA), claimed to have performed a quantum computation that was infeasible on any classical computer.
    
    There are several types of quantum computers (also known as quantum computing systems), including the quantum circuit model, quantum Turing machine, adiabatic quantum computer, one-way quantum computer, and various quantum cellular automata. The most widely used model is the quantum circuit, based on the quantum bit, or "qubit", which is somewhat analogous to the bit in classical computation. A qubit can be in a 1 or 0 quantum state, or in a superposition of the 1 and 0 states. When it is measured, however, it is always 0 or 1; the probability of either outcome depends on the qubit's quantum state immediately prior to measurement.
    """,
    
    "blockchain_technology": """
    A blockchain is a distributed ledger with growing lists of records (blocks) that are securely linked together via cryptographic hashes. Each block contains a cryptographic hash of the previous block, a timestamp, and transaction data (generally represented as a Merkle tree, where data nodes are represented by leaves). The timestamp proves that the transaction data existed when the block was created. Since each block contains information about the previous block, they effectively form a chain (compare linked list data structure), with each additional block linking to the ones before it. Consequently, blockchain transactions are irreversible in that, once they are recorded, the data in any given block cannot be altered retroactively without altering all subsequent blocks.
    
    Blockchains are typically managed by a peer-to-peer (P2P) computer network for use as a public distributed ledger, where nodes collectively adhere to a consensus algorithm protocol to add and validate new transaction blocks. Although blockchain records are not unalterable, since blockchain forks are possible, blockchains may be considered secure by design and exemplify a distributed computing system with high Byzantine fault tolerance.
    
    The blockchain was popularized by a person (or group of people) using the name Satoshi Nakamoto in 2008 to serve as the public distributed ledger for bitcoin cryptocurrency transactions, based on work by Stuart Haber, W. Scott Stornetta, and Dave Bayer. The identity of Satoshi Nakamoto remains unknown to date. The implementation of the blockchain within bitcoin made it the first digital currency to solve the double-spending problem without the need of a trusted authority or central server. The bitcoin design has inspired other applications and blockchains that are readable by the public and are widely used by cryptocurrencies. The blockchain is considered a type of payment rail.
    
    Private blockchains have been proposed for business use. Computerworld called the marketing of such privatized blockchains without a proper security model "snake oil"; however, others have argued that permissioned blockchains, if carefully designed, may be more decentralized and therefore more secure in practice than permissionless ones.
    """,
    
    "machine_learning": """
    Machine learning (ML) is a field of inquiry devoted to understanding and building methods that 'learn', that is, methods that leverage data to improve performance on some set of tasks. It is seen as a part of artificial intelligence. Machine learning algorithms build a model based on sample data, known as training data, in order to make predictions or decisions without being explicitly programmed to do so. Machine learning algorithms are used in a wide variety of applications, such as in medicine, email filtering, speech recognition, and computer vision, where it is difficult or unfeasible to develop conventional algorithms to perform the needed tasks.
    
    A subset of machine learning is closely related to computational statistics, which focuses on making predictions using computers, but not all machine learning is statistical learning. The study of mathematical optimization delivers methods, theory and application domains to the field of machine learning. Data mining is a related field of study, focusing on exploratory data analysis through unsupervised learning. Some implementations of machine learning use data and neural networks in a way that mimics the working of a biological brain. In its application across business problems, machine learning is also referred to as predictive analytics.
    
    Learning algorithms work on the basis that strategies, algorithms, and inferences that worked well in the past are likely to continue working well in the future. These inferences can be obvious, such as "since the sun rose every morning for the last 10,000 days, it will probably rise tomorrow morning as well". They can be nuanced, such as "X% of families have geographically separate species with color variants, so there is a Y% chance that undiscovered black swans exist".
    
    Machine learning programs can perform tasks without being explicitly programmed to do so. It involves computers learning from data provided so that they carry out certain tasks. For simple tasks assigned to computers, it is possible to program algorithms telling the machine how to execute all steps required to solve the problem at hand; on the computer's part, no learning is needed. For more advanced tasks, it can be challenging for a human to manually create the needed algorithms. In practice, it can turn out to be more effective to help the machine develop its own algorithm, rather than having human programmers specify every needed step.
    """,
    
    "nutrition_science": """
    Nutrition is the biochemical and physiological process by which an organism uses food to support its life. It provides organisms with nutrients, which can be metabolized to create energy and chemical structures. Failure to obtain sufficient nutrients causes malnutrition. Nutritional science is the study of nutrition, though it typically emphasizes human nutrition.
    
    The type of organism determines what nutrients it needs and how it obtains them. Organisms obtain nutrients by consuming organic matter, consuming inorganic matter, absorbing light, or some combination of these. Some can produce nutrients internally by consuming basic elements, while some must consume other organisms to obtain pre-made nutrients. All forms of life require carbon, hydrogen, oxygen, nitrogen, and phosphorus, and various other elements (potassium, calcium, iron, magnesium, etc.) are necessary for specific organisms.
    
    Nutritional groups are a method of classifying organisms, specifically microorganisms, based on the source(s) of the carbon and other nutrients they need to live and the source and mechanism by which energy is acquired for that nutrition. For phototrophs, the source of energy is light, whereas for chemotrophs, it is the chemical oxidation of organic (organotrophs) or inorganic (lithotrophs) compounds. Similarly, to build up new organic compounds, organisms can use carbon dioxide (CO2) (autotrophs) or organic compounds from their environment (heterotrophs).
    
    Nutrients are substances used by an organism to survive, grow, and reproduce. The seven major classes of relevant nutrients for animals (including humans) are carbohydrates, fiber, fats, proteins, minerals, vitamins, and water. Nutrients can be grouped as either macronutrients (carbohydrates, fiber, fats, proteins, and water needed in gram quantities) or micronutrients (vitamins, and minerals needed in milligram or microgram quantities).
    
    Food provides nutrients that are needed for survival, growth, and reproduction. For humans in particular, a healthy diet is a diet that contains the necessary nutrients to perform these functions while avoiding diseases such as metabolic syndrome. Since humans evolved as omnivorous hunter-gatherers, many adaptations to a purely animal-based diet and a purely plant-based diet exist, although humans did not evolve to consume other products, such as dairy from other species.
    """,
    
    "space_exploration": """
    Space exploration is the use of astronomy and space technology to explore outer space. While the study of space is carried out mainly by astronomers with telescopes, its physical exploration though is conducted both by unmanned robotic space probes and human spaceflight. Space exploration, like its classical form astronomy, is one of the main sources for space science.
    
    While the observation of objects in space, known as astronomy, predates reliable recorded history, it was the development of large and relatively efficient rockets during the mid-twentieth century that allowed physical space exploration to become a reality. Common rationales for exploring space include advancing scientific research, national prestige, uniting different nations, ensuring the future survival of humanity, and developing military and strategic advantages against other countries.
    
    The early era of space exploration was driven by a "Space Race" between the Soviet Union and the United States. The launch of the first human-made object to orbit Earth, the Soviet Union's Sputnik 1, on 4 October 1957, and the first Moon landing by the American Apollo 11 mission on 20 July 1969 are often taken as landmarks for this initial period. The Soviet space program achieved many of the first milestones, including the first living being in orbit in 1957, the first human spaceflight (Yuri Gagarin aboard Vostok 1) in 1961, the first spacewalk (by Alexei Leonov) on 18 March 1965, the first automatic landing on another celestial body in 1966, and the launch of the first space station (Salyut 1) in 1971. After the first 20 years of exploration, focus shifted from one-off flights to renewable hardware, such as the Space Shuttle program, and from competition to cooperation as with the International Space Station (ISS).
    
    With the substantial completion of the ISS following STS-133 in March 2011, plans for space exploration by the US remain in flux. Constellation, a Bush Administration program for a return to the Moon by 2020 was judged inadequately funded and unrealistic by an expert review panel reporting in 2009. The Obama Administration proposed a revision of Constellation in 2010 to focus on the development of the capability for crewed missions beyond low Earth orbit (LEO), envisioning extending the operation of the ISS beyond 2020, transferring the development of launch vehicles for human crews from NASA to the private sector.
    """,
    
    "cybersecurity": """
    Computer security, cybersecurity, or information technology security (IT security) is the protection of computer systems and networks from information disclosure, theft of, or damage to their hardware, software, or electronic data, as well as from the disruption or misdirection of the services they provide.
    
    The field is becoming increasingly significant due to the continuously expanding reliance on computer systems, the Internet, and wireless network standards such as Bluetooth and Wi-Fi, and due to the growth of "smart" devices, including smartphones, televisions, and the various devices that constitute the Internet of things (IoT). Cybersecurity is one of the most significant challenges of the contemporary world, due to both the complexity of information systems and the societies they support. Security is of especially high importance for systems that govern large-scale systems with far-reaching physical effects, such as power distribution, elections, and finance.
    
    Cybersecurity is not just about securing information. That is the definition of Information Assurance (IA). Cybersecurity is about securing the organizations that depend on the information. Many components of cybersecurity overlap with information assurance, though cybersecurity is a deeper level of security compared to IA.
    
    Even systems designed with security in mind often have weaknesses (also known as security vulnerabilities). Sometimes this is a programming error like a buffer overflow attack or SQL injection. Many of these types of issues can be fixed with patches from the software vendor. The major categories of attack types are Distributed Denial of Service attacks (DDoS) in which a service is rendered unavailable for a period due to malicious attack; Data breaches and password attacks, in which an attacker may gain unauthorized access and breach sensitive data; Man in the middle attacks, in which a third party may duplicate and spoof a site to acquire sensitive information such as passwords; and Memory-based attacks, such as side-channel data attacks, which target caches and physical RAM to gain unauthorized access to sensitive data.
    
    Since the same computer code is used in multiple places, a vulnerability in one part of the code may lead to the vulnerability of all IT systems using that code. And since IT connects to nearly all parts of an organization, a vulnerability in one part of the organization's systems may allow attackers to penetrate other systems. IT systems affect the physical world constantly: unlocking doors, maintaining temperature, etc. That fact combined with various vulnerabilities could lead to affecting the physical world through IT systems.
    """,
    
    "biotechnology": """
    Biotechnology is a broad area of biology, involving the use of living systems and organisms to develop or make products. Depending on the tools and applications, it often overlaps with related scientific fields. In the late 20th and early 21st centuries, biotechnology has expanded to include new and diverse sciences, such as genomics, recombinant gene techniques, applied immunology, and development of pharmaceutical therapies and diagnostic tests. The term biotechnology was first used by Karl Ereky in 1919, meaning the production of products from raw materials with the aid of living organisms.
    
    For thousands of years, humankind has used biotechnology in agriculture, food production, and medicine. The term itself is largely believed to have been coined in 1919 by Hungarian engineer Károly Ereky. In the late 20th and early 21st centuries, biotechnology has expanded to include new and diverse sciences, such as genomics, recombinant gene techniques, applied immunology, and development of pharmaceutical therapies and diagnostic tests. The wide concept of "biotech" or "biotechnology" encompasses a wide range of procedures for modifying living organisms according to human purposes, going back to domestication of animals, cultivation of the plants, and "improvements" to these through breeding programs that employ artificial selection and hybridization. Modern usage also includes genetic engineering as well as cell and tissue culture technologies.
    
    Biotechnology is the research and development in the laboratory using bioinformatics for exploration, extraction, exploitation and production from any living organisms and any source of biomass by means of biochemical engineering where high value-added products could be planned (reproduced by biosynthesis, for example), forecasted, formulated, developed, manufactured, and marketed for the purpose of sustainable operations (for the return from bottomless initial investment on R & D) and gaining durable patents rights (for exclusives rights for sales, and prior to this to receive national and international approval from the results on animal experiment and human experiment, especially on the pharmaceutical branch of biotechnology to prevent any undetected side-effects or safety concerns by using the products).
    
    By contrast, bioengineering is generally thought of as a related field that more heavily emphasizes higher systems approaches (not necessarily the altering or using of biological materials directly) for interfacing with and utilizing living things. Bioengineering is the application of the principles of engineering and natural sciences to tissues, cells and molecules. This can be considered as the use of knowledge from working with and manipulating biology to achieve a result that can improve functions in plants and animals. Relatedly, biomedical engineering is an overlapping field that often draws upon and applies biotechnology (by various definitions), especially in certain sub-fields of biomedical or chemical engineering such as tissue engineering, biopharmaceutical engineering, and genetic engineering.
    """
}

# Create PDFs
for i, (topic, content) in enumerate(TOPICS.items(), 1):
    # Determine random word count between 500-5000
    target_word_count = random.randint(500, 5000)
    
    # Adjust content to meet target word count
    words = content.split()
    if len(words) > target_word_count:
        # Truncate content if it's too long
        content = ' '.join(words[:target_word_count])
    else:
        # Repeat content if it's too short
        multiplier = (target_word_count // len(words)) + 1
        content = ' '.join(words * multiplier)[:target_word_count * 6]  # Approximate character count
    
    # Create PDF
    pdf_file = f"data/test_{i:02d}_{topic}.pdf"
    
    # Initialize PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Add a title
    pdf.set_font("Arial", style="B", size=16)
    title = f"Test Document {i}: {topic.replace('_', ' ').title()}"
    pdf.cell(0, 10, title, ln=True, align="C")
    pdf.ln(10)
    
    # Reset font for body text
    pdf.set_font("Arial", size=12)
    
    # Add content - wrapped to fit page width
    wrapped_text = textwrap.fill(content, width=80)
    for line in wrapped_text.split('\n'):
        pdf.multi_cell(0, 10, line)
    
    # Save the PDF
    pdf.output(pdf_file)
    
    # Display information about the created file
    word_count = len(content.split())
    print(f"Created: {pdf_file} with approximately {word_count} words")

print("\nAll 10 PDF files have been created in the 'data' directory") 