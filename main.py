from src import create_app

app = create_app()

if __name__=="main":
	app.run(host='0.0.0.0', port=80, debug=True, threaded=True)
