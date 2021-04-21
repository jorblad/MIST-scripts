import paramiko
import yaml

with open('Switches/config.yaml') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

switch_username = config['switch']['username']
switch_password = config['switch']['password']
print('This script will ask for another IP-address until you press ctrl+c\n')
while True:
    try:
        switch_ip = input('Enter IP-address: ')

        ssh = paramiko.SSHClient()

        # Load SSH host keys.
        ssh.load_system_host_keys()
        # Add SSH host key automatically if needed.
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(switch_ip, username=switch_username, password=switch_password, look_for_keys=False)
        except:
            print("[!] Cannot connect to the SSH Server")
            exit()

        stdin, stdout, stderr = ssh.exec_command(
            'request system configuration rescue save\n')
        print(stdout.read())
        stdin, stdout, stderr = ssh.exec_command(
            'request system reboot slice alternate media internal at 22\n')
        print(stdout.read())


        ssh.close()

    except Exception as e:
        print(e)
