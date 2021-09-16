import motor.motor_asyncio
URL="mongodb+srv://subinps:subinps@cluster0.s4eok.mongodb.net/myFirstDatabase?retryWrites=true&w=majority"
COLLECTION="VideoPlayerConfig"

class Database:    
    def __init__(self):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(URL)
        self.db = self._client[COLLECTION]
        self.col = self.db.config    
    def new_config(self, name, value):
        return dict(
            name = name,
            value = value,
        )   
    async def add_config(self, name, value):
        user = self.new_user(name, value)
        await self.col.insert_one(user)
    
    
    async def is_saved(self, name):
        user = await self.col.find_one({'name':name})
        return True if user else False
     
    async def edit_config(self, name, value):
        await self.col.update_one({'name': name}, {'$set': {'value': value}})

    async def get_config(self, name):
        config = await self.col.find_one({'name':name})
        return config.get('value', None)
    
