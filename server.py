#!flask/bin/python
from flask import Flask, jsonify, request, Response, render_template, send_from_directory#, send_file
from flask_socketio import SocketIO, emit

# from queue import Queue
import urllib, os, sys, random, math, json
from time import localtime, strftime
from pathlib import Path#, PureWindowsPath

from src.objects import Input, GHClient, Context, Logger
from src.job import Job
from src.utils import remap


app = Flask(__name__)
app.config['SECRET_KEY'] = 'key1234'
socketio = SocketIO(app)

# context = Context(os.path.dirname(os.path.abspath(__file__)), sys.platform)
context = Context()
gh = GHClient()
logger = Logger()

job = None
# des = Design(None, None, None, logger)


@app.route("/")
def index():
	return render_template("index.html")


@app.route('/api/v1.0/connect/<string:fileName>', methods=['GET'])
def connect(fileName):
	local_file = urllib.parse.unquote(fileName)

	file_path = local_file.split("\\")
	file_dir = "\\".join(file_path[:-1])
	file_name = file_path[-1].split(".")[0]

	# lp = "\\".join(fn.split("\\")[:-1])

	local_dir = Path(file_dir) / "discover"

	# ping_file_names = ["0", "1"]

	# print(fn)

	context.connect(local_dir)
	# gh.connect(fn, ping_file_names, context.get_server_path([]))
	gh.connect(local_dir, file_name)
	# gh.ping(0)

	gather_inputs()

	logger.init(local_dir)
	message = "Connected to Grasshopper file: {}".format(file_name)
	socketio.emit('server message', {"message": message})
	logger.log(message)

	# local_ping_paths = ["\\".join([context.get_local_path([]), "data", "temp", fn]) for fn in gh.ping_file_names]

	return jsonify({'status': 'Server connected'})#, 'connections': gh.get_local_pingPaths(context.get_local_path([]))})

# @app.route("/api/v1.0/test/", methods=['GET', 'POST'])
def gather_inputs():
	if not gh.is_connected():
		return jsonify({"status": "fail"})

	# job_spec = request.json
	# options = job_spec["options"]

	gh.clear_inputs()

	d = gh.get_dir(["temp"])
	files = [file for file in os.listdir(d) if file.split(".")[0] == gh.get_name()]
	for file in files:
		gh.ping(file)

	# des.generate_random(job_spec["inputs"])
	# gh.ping(0)

	message = "Generated test inputs"
	# message = str("_".join(files))
	socketio.emit('server message', {"message": message})

	return jsonify({"status": "success"})

@app.route("/api/v1.0/start/", methods=['GET', 'POST'])
def start_optimization():
	global job

	if not gh.is_connected():
		return jsonify({"status": "fail"})

	job_spec = request.json
	print(job_spec)
	options = job_spec["options"]

	job = Job(options, gh.get_name(), gh.get_dir([]), logger)
	job.init_inputs(gh.get_inputs())
	job.init_outputs(gh.get_outputs())
	job.init_data_file()
	job.init_first_gen()

	gh.ping_inputs()

	message = "Optimization started: {} designs / {} generations".format(job.num_designs, job.max_gen)
	socketio.emit('server message', {"message": message})

	return jsonify({"status": "success", "job_id": job.job_id})

@app.route("/api/v1.0/stop/", methods=['GET'])
def stop_optimization():
	global job

	if job is None or not job.is_running():
		return jsonify({"status": "fail"})
	else:
		job.running = False
		message = "Job terminated."
		socketio.emit('server message', {"message": message})
		logger.log(message)

	return jsonify({"status": "success", "job_id": job.job_id})

@app.route("/api/v1.0/get_ss_path/", methods=['GET'])
def get_ss_path():
	if job is not None and job.is_running():
		des = job.get_latest_des()
		des_id = des.get_id()

		local_path = context.get_local_path(["data"])

		ss_path = "\\".join([local_path, job.get_id(), "images", str(des_id)])
		return jsonify({'status': 'success', 'path': ss_path})
	else:
		return jsonify({"status": "fail"})

@app.route("/api/v1.0/job_running/", methods=['GET'])
def job_running():
	if job is not None and job.is_running():
		return jsonify(True)
	else:
		return jsonify(False)

@app.route("/api/v1.0/get_input/", methods=['GET', 'POST'])
def get_input():

	json_in = request.json
	input_id = json_in["id"]
	input_def = json.loads(json_in["input_def"])

	if job is not None and job.is_running():
		return jsonify({"status": "Received design input from server", "vals": job.get_next(input_id)})
		# return jsonify(job.get_next())
	else:
		new_input = Input(input_id, input_def)
		return jsonify({"status": "Received random input from server", "vals": new_input.generate_random()})

@app.route("/api/v1.0/ack_input/", methods=['GET', 'POST'])
def ack_input():
	json_in = request.json
	input_id = json_in["id"]
	input_def = json.loads(json_in["input_def"])

	if job is None or not job.is_running():
		new_input = Input(input_id, input_def)
		gh.add_input(input_id, new_input)
		return jsonify({'status': 'registered input {} with Discover'.format(input_id)})

	gh.lift_block(input_id)
	return jsonify({'status': 'success - lifted block on input {}'.format(input_id)})

# @app.route("/api/v1.0/get_inputs/", methods=['GET'])
# def get_inputs():
# 	if job is not None and job.is_running():
# 		return jsonify(job.get_next())
# 	else:
# 		return jsonify(des.get_inputs())

@app.route('/api/v1.0/set_outputs/', methods=['GET', 'POST'])
def set_outputs():

	outputs = request.json

	if job is None or not job.is_running():
		gh.set_outputs(outputs)
		return jsonify({'status': 'No job running'})

	if gh.check_block():
		return jsonify({'status': 'Process blocked'})

	

	# if job.is_running():
	job.set_outputs(outputs)
	
		# if job.get_spec()["options"]["Save screenshot"]:
			# gh.ping(1)
			# return jsonify({'status': 'Waiting for screenshot...'})
		# else:
	return do_next()

	# else:
		# job.init_inputs(gh.get_inputs())
		# job.init_outputs(outputs)
		# job.run()
		# gh.ping_inputs()
		# return jsonify({'status': 'Gathered inputs.'})

@app.route('/api/v1.0/ss_done/', methods=['GET'])
def ss_done():
	if job is None or not job.is_running():
		return jsonify({'status': 'No job running'})
	return do_next()

def do_next():
	run, message = job.run_next()

	if message is not None:
		socketio.emit('server message', {"message": message})

	if run:
		gh.ping_inputs()
		return jsonify({'status': 'Job running...'})
	else:
		job.running = False
		logger.log("Job finished.")

		return jsonify({'status': 'No job running'})



@app.route('/api/v1.0/get_data/<string:job_name>', methods=['GET'])
def get_data(job_name):

	data_path = context.get_server_path(["data"]) / job_name / "results.tsv"
	if not data_path.exists():
		return jsonify({"status": "fail"})

	image_path = context.get_server_path(["data"]) / job_name / "images"

	json_out = []

	with open(data_path, 'r') as f:
		lines = f.readlines()

	header = lines.pop(0).split("\t")

	for line in lines:
		d = line.split("\t")
		json_out.append({header[i]: d[i] for i in range(len(d)) })

	message = "Loaded data from server: {}".format(job_name)
	socketio.emit('server message', {"message": message})

	return json.dumps({"status": "success", "load_images": image_path.exists(), "data": json_out})


@app.route('/api/v1.0/get_design/<string:job_name>/<string:des_id>', methods=['GET'])
def get_design(job_name, des_id):
	if not gh.is_connected():
		return jsonify({"status": "no-gh"})
	if job is not None:
		if job.is_running():
			return jsonify({"status": "job-running"})

	data_path = context.get_server_path(["data"]) / job_name / "results.tsv"
	if not data_path.exists():
		return jsonify({"status": "fail"})

	with open(data_path, 'r') as f:
		lines = f.readlines()

	header = lines.pop(0).split("\t")

	ids = [line.split("\t")[0] for line in lines]
	des_loc = ids.index(des_id)

	d = lines[des_loc].split("\t")

	inputs = [ json.loads(d[i]) for i in range(len(d)) if "[Continuous]" in header[i] or "[Categorical]" in header[i] or "[Sequence]" in header[i] ]

	des.set_inputs(inputs)
	gh.ping(0)

	message = "Reinstated design {} from {}".format(des_id, job_name)
	socketio.emit('server message', {"message": message})

	return jsonify({"status": "success"})


@app.route("/api/v1.0/get_image/<string:job_name>/<string:des_id>", methods=['GET'])
def get_image(job_name, des_id):
	image_path = context.get_server_path(["data"]) / job_name / "images" 
	return send_from_directory(image_path, des_id + '.png')

def ack():
	print('message was received!', file=sys.stderr)

@socketio.on('client message')
def handle_my_custom_event(json):
	print('received json: ' + str(json), file=sys.stderr)
	emit('server message', json, callback=ack)

if __name__ == '__main__':
	socketio.run(app, debug=True, host='0.0.0.0', port=5000)