"""
Allow customizing cluster size, node names, dataset, and disk image.
"""

import geni.urn as urn
import geni.portal as portal
import geni.rspec.pg as rspec
import geni.aggregate.cloudlab as cloudlab
import json

# The possible set of base disk-images that this cluster can be booted with.
# The second field of every tupule is what is displayed on the cloudlab
# dashboard.
images = [
    ("emulab-ops:UBUNTU22-64-STD", "Ubuntu 22.04 (64-bit)"),
    ("emulab-ops:UBUNTU20-64-STD", "Ubuntu 20.04 (64-bit)"),
    ("emulab-ops:UBUNTU18-64-STD", "Ubuntu 18.04 (64-bit)"),
    ("emulab-ops:UBUNTU16-64-STD", "Ubuntu 16.04 (64-bit)"),
    ("knativeext-PG0:k8s-dev", "Kubernetes Dev"),
]

# The possible set of node-types this cluster can be configured with.
nodes = {
    "xl170": ("xl170", "Utah xl170 (64 GB RAM, 10 cores E5-2640v4, Mellanox ConnectX-4)"),
    "m510": ("m510", "Utah m510 (64 GB RAM, 8 cores Xeon-D, Mellanox ConnectX-3)"),
    "c6525-25g": ("c6525-25g", "Utah c6525-25g (128 GB RAM, 16 cores AMD EPYC 7302P)"),
    "c6525-100g": ("c6525-100g", "Utah c6525-100g (128 GB RAM, 24 cores AMD EPYC 7402P)"),
    "d6515": ("d6515", "Utah d6515 (128 GB RAM, 32 cores AMD EPYC 7452)"),
}
# ("rs630", "UMASS rs630 (256 GB RAM, 10 cores Xeon E5-2660"),
# ("sm110p", "WISCONSIN sm110p (128 GB RAM, 16 cores Xeon Silver 4314"),
# ("d430", "Emulab d430 (64GB RAM, 8 cores Xeon E5 2630v3, 10 Gbps Intel Ethernet)"),

# Allows for general parameters like disk image to be passed in. Useful for
# setting up the cloudlab dashboard for this profile.
context = portal.Context()

# Default the disk image to 64-bit Ubuntu 16.04
context.defineParameter("image", "Disk Image",
                        portal.ParameterType.STRING, images[0], [],
                        "Specify the base disk image that all the nodes of the cluster " +
                        "should be booted with.")

# Default the master node type to the d6515.
context.defineParameter("mType", "Master Node Type",
                        portal.ParameterType.NODETYPE, nodes["d6515"])

context.defineParameter("mName", "Hostname(prefix) of Master Nodes",
                        portal.ParameterType.STRING, "master")

context.defineParameter("mCount", "# of Master Nodes",
                        portal.ParameterType.INTEGER, 1)

# Default the node type to the xl170.
context.defineParameter("wType", "Worker Node Type",
                        portal.ParameterType.NODETYPE, nodes["xl170"])

context.defineParameter("wName", "Hostname(prefix) of Worker Nodes",
                        portal.ParameterType.STRING, "worker")

context.defineParameter("wCount", "# of Worker Nodes",
                        portal.ParameterType.INTEGER, 3)

# context.defineParameter("roles", "Roles and # of Nodes",
#                         portal.ParameterType.STRING, "{}", [],
#                         "Specify the roles and the number of nodes assuming each role. \
#                         Should be a valid json str, example: {\"gateway\": 1, \"controller\": 3, \"worker\": 3}")

context.defineParameter("storage", "Extra Disk Space (GB)",
                        portal.ParameterType.INTEGER, 64)

context.defineParameter("smnt", "Mount Point for Extra Disk",
                        portal.ParameterType.STRING, "/workspace")

context.defineParameter("dataset", "Dataset Name",
                        portal.ParameterType.STRING, "")

context.defineParameter("dsize", "Dataset Size (GB)",
                        portal.ParameterType.INTEGER, 64)

context.defineParameter("dmnt", "Mount Point for Dataset",
                        portal.ParameterType.STRING, "")

params = context.bindParameters()

# names_json = json.loads(params.roles)
# hostnames = []
# for name, cnt in names_json.items():
#     for i in range(cnt):
#         hostnames.append(name + str(i+1))

masters = [params.mName + str(i+1) for i in range(params.mCount)]
workers = [params.wName + str(i+1) for i in range(params.wCount)]
hostnames = masters + workers

request = rspec.Request()

# Create two LANs (non-overlapping CIDRs) over a 10 Gbps.
# LAN1: 10.10.0.0/24, LAN2: 10.20.0.0/24
lan1 = rspec.LAN("lan1")
lan1.bandwidth = 10000000  # This is in kbps.
lan1.best_effort = True
lan1.link_multiplexing = True

lan2 = rspec.LAN("lan2")
lan2.bandwidth = 10000000  # This is in kbps.
lan2.best_effort = True
lan2.link_multiplexing = True

# Setup the cluster one node at a time.
for i in range(len(hostnames)):
    node = rspec.RawPC(hostnames[i])

    if params.mName in hostnames[i]:
        node.hardware_type = params.mType
    else:
        node.hardware_type = params.wType

    node.disk_image = urn.Image(cloudlab.Utah, params.image)

    if len(params.smnt) > 0:
        bs = node.Blockstore("bs"+str(i), params.smnt)
        bs.size = str(params.storage) + 'GB'

    if len(params.dmnt) > 0:
        ds = node.Blockstore("ds"+str(i), params.dmnt)
        ds.size = str(params.dsize) + 'GB'
        if len(params.dataset) > 0:
            ds.dataset = "urn:publicid:IDN+utah.cloudlab.us:knativeext-pg0+imdataset+"+params.dataset

    # # Install and run the startup scripts.
    # if len(params.script) > 0:
    #     node.addService(rspec.Install(
    #         url="https://github.com/TomQuartz/cloudlab-setup/archive/main.tar.gz", path="/local"))
    #     node.addService(rspec.Execute(
    #         shell="bash", command="sudo mv /local/cloudlab-setup-main /local/cloudlab-setup"))
    #     script = os.path.join("/local/cloudlab-setup", params.script)
    #     node.addService(rspec.Execute(
    #         shell="bash", command="sudo %s 2>&1 | sudo tee /local/logs/setup.log" % script))

    node.addService(rspec.Install(
        url="https://github.com/SMALL-head/cloudlab-file/releases/download/test-v3/setup.tar.gz",
        path="/local"
    ))
    node.addService(rspec.Execute(
        shell="bash",
        command=(
            "sudo env "
            f"MASTER_PREFIX={params.mName} "
            f"WORKER_PREFIX={params.wName} "
            "NFS_SERVER_IP=192.168.31.2 "
            "NFS_EXPORT=/cluster-nfs "
            "NFS_SUBNET=* "
            "bash /local/setup.bash"
        )
    ))

    request.addResource(node)

    # Pre-boot execution: install baseline tools on each node
    # node.addService(rspec.Execute(
    #     shell="bash",
    #     command="sudo apt-get update && sudo apt-get install -y curl net-tools vim git"
    # ))

    # Add two data-plane interfaces per node, one into each LAN with explicit IPs.
    # LAN1 (192.168.31.0/24)
    iface1 = node.addInterface("if1")
    iface1.addAddress(rspec.IPv4Address("192.168.31.%d" % (i + 2), "255.255.255.0"))
    lan1.addInterface(iface1)

    # LAN2 (192.169.31.0/24)
    iface2 = node.addInterface("if2")
    iface2.addAddress(rspec.IPv4Address("192.169.31.%d" % (i + 2), "255.255.255.0"))
    lan2.addInterface(iface2)

# Add the LANs to the request.
request.addResource(lan1)
request.addResource(lan2)

# Generate the RSpec
context.printRequestRSpec(request)
