from src import create_app

app = create_app()

if __name__ == "__main__":
	app.run(debug=True, port=8000) # debug=True only for development purpose

# remove comments when upload into live server
'''
if __name__=="main":
	app.run()
'''