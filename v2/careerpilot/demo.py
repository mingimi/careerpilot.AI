from .core import normalize
# v1 fictional company fixtures retained, explicitly isolated from live storage.
def jobs():
    return [normalize('Northstar Labs (DEMO)','demo','1','AI Product Analyst','Use SQL, Product Analytics, Communication and GenAI. 1 year of experience. Build AI products.','Bengaluru, India','', 'Full-time'),
            normalize('BrightCart (DEMO)','demo','2','Growth Marketing Associate','Use Marketing, Excel, SEO and Communication. 0 years of experience. Run growth experiments.','Mumbai, India','', 'Full-time'),
            normalize('GreenGrid (DEMO)','demo','3','Product Operations Associate','Use User Research, Excel and Project Management. 2 years of experience.','Remote, India','', 'Full-time')]
